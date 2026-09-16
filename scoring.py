"""
Scoring & classification.

Takes the combined raw results from all four sources and:
  1. classifies each as Type A (engagement opportunity) or Type B (build signal),
  2. scores Type A items, and
  3. ranks the strongest into the daily top-N list.

Deterministic and heuristic — no live API needed — so it can be tested against
sample data before wiring live sources in (per the spec's testing approach).
"""
import re

from config import TOPICS_AND_NICHES, TOP_N

# Words/phrases that indicate a real person asking / voicing a pain — Type A signal.
QUESTION_MARKERS = [
    "?", "how do i", "how can i", "how to", "what is the best", "which tool",
    "any recommendations", "anyone know", "help", "struggling", "stuck",
    "advice", "should i", "looking for", "suggestions", "recommend",
]

PAIN_MARKERS = [
    "struggling", "frustrated", "hate", "can't", "cannot", "waste", "wasting",
    "overwhelmed", "confused", "too many", "no idea", "problem", "pain",
    "difficult", "hard to", "tired of", "annoying", "broken", "fail",
]

# Hosts that ARE real discussions you can jump into (so a Google/Perplexity hit
# pointing here can still be a Type A engagement opportunity, not just a signal).
DISCUSSION_HOSTS = ["reddit.com", "quora.com", "stackoverflow.com", "stackexchange.com",
                    "news.ycombinator.com", "indiehackers.com", "producthunt.com"]

# Niche keywords used to measure relevance.
_NICHE_WORDS = set()
for t in TOPICS_AND_NICHES:
    for w in re.split(r"\W+", t.lower()):
        if len(w) > 2:
            _NICHE_WORDS.add(w)


def _text_of(r) -> str:
    return f"{r.title} {r.summary} {r.raw_snippet}".lower()


def _has_any(text, markers) -> bool:
    return any(m in text for m in markers)


def _count_any(text, markers) -> int:
    return sum(1 for m in markers if m in text)


def _relevance(text) -> int:
    return sum(1 for w in _NICHE_WORDS if w in text)


def _is_discussion_url(url) -> bool:
    u = (url or "").lower()
    return any(h in u for h in DISCUSSION_HOSTS)


def _is_real_thread(url) -> bool:
    """True only for a specific post/thread/article — never a bare homepage or
    subreddit landing page (those are useless: nothing to reply to)."""
    from urllib.parse import urlparse
    u = (url or "").lower().strip()
    if not u:
        return False
    if "reddit.com" in u:
        return "/comments/" in u          # a real thread, not r/sub/ or reddit.com/
    if "news.ycombinator.com" in u:
        return "item?id=" in u             # a real HN item, not the front page
    path = urlparse(u).path.strip("/")
    return len(path) > 4                    # generic: must have a real content path


def classify(r):
    """Set r.result_type to 'A' or 'B' and, for B, record the observed pattern."""
    text = _text_of(r)
    looks_like_question = _has_any(text, QUESTION_MARKERS)

    # Reddit / Quora items are real conversations → Type A engagement opportunities.
    if r.source in ("reddit", "quora"):
        r.result_type = "A"
        return

    # Google / Perplexity are search-surfaced. If they point at a real discussion
    # AND read like a question, they're still an engageable Type A. Otherwise they
    # represent a demand pattern → Type B build signal.
    if _is_discussion_url(r.url) and looks_like_question:
        r.result_type = "A"
    else:
        r.result_type = "B"
        # Prefer the actual surfaced discussion title (specific); fall back to the
        # search-query theme only if there's no real title.
        title = (r.title or "").strip()
        m = re.search(r"QUERY:\s*(.+)", r.raw_snippet)
        q = (m.group(1).strip() if m else "")
        r.pattern = title if len(title) > 15 else (q or title)


def score_type_a(r) -> float:
    """0–100 composite: relevance + pain intensity + question-ness + recency + engageability."""
    text = _text_of(r)
    relevance = min(_relevance(text), 6) / 6.0 * 40          # up to 40
    pain = min(_count_any(text, PAIN_MARKERS), 4) / 4.0 * 30  # up to 30
    questionness = 20 if _has_any(text, QUESTION_MARKERS) else 0  # 20
    engageable = 10 if r.source in ("reddit", "quora") or _is_discussion_url(r.url) else 0  # 10
    return round(relevance + pain + questionness + engageable, 1)


def classify_and_score(results, logger):
    """Classify all, score+rank Type A, return (type_a_top, type_a_all, type_b)."""
    # Drop junk URLs (bare homepages / subreddit landing pages) up front — there's
    # nothing to reply to on those.
    before = len(results)
    results = [r for r in results if _is_real_thread(r.url)]
    dropped = before - len(results)
    if dropped:
        logger.info(f"Scoring: dropped {dropped} non-thread/homepage URLs.")

    for r in results:
        classify(r)

    type_a = [r for r in results if r.result_type == "A"]

    # De-duplicate Type B build signals by their pattern/title so the same theme
    # doesn't repeat (e.g. "best AI tool for solo entrepreneurs" x5).
    type_b = []
    seen_b = set()
    for r in results:
        if r.result_type != "B":
            continue
        k = (r.pattern or r.title or "").strip().lower()
        if not k or k in seen_b:
            continue
        seen_b.add(k)
        type_b.append(r)

    for r in type_a:
        r.score = score_type_a(r)

    # De-duplicate Type A by the underlying thread (Reddit thread id, else URL),
    # keeping the highest score — catches the same thread with different slug formatting.
    def _dedup_key(url):
        u = (url or "").lower()
        m = re.search(r"/comments/([a-z0-9]+)", u)
        return "reddit:" + m.group(1) if m else u.rstrip("/")

    best = {}
    for r in sorted(type_a, key=lambda x: x.score, reverse=True):
        k = _dedup_key(r.url) or id(r)
        if k in best:
            continue
        best[k] = r
    type_a_sorted = sorted(best.values(), key=lambda x: x.score, reverse=True)

    top = type_a_sorted[:TOP_N]
    for i, r in enumerate(top, 1):
        r.rank = i

    logger.info(f"Scoring: {len(type_a_sorted)} Type A opportunities, "
                f"{len(type_b)} Type B build signals. Top {len(top)} selected.")
    return top, type_a_sorted, type_b
