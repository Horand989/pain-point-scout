"""
Reddit source — official API (PRAW) as PRIMARY, ScrapingBee as FALLBACK.

If you have the official Reddit key it uses that (free). If you don't yet
(pending approval) OR it returns nothing, it falls back to ScrapingBee hitting
Reddit's own search.json — so Reddit results come through either way.
Never crashes the run.
"""
import os
from datetime import datetime, timezone

from .base import Result
from . import scrapingbee


def _official(queries, limits, logger):
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "pain-point-scout/0.1")
    if not client_id or not client_secret:
        return None  # signal: no official creds
    try:
        import praw
    except ImportError:
        logger.error("Reddit: praw not installed — falling back to ScrapingBee.")
        return None
    try:
        reddit = praw.Reddit(client_id=client_id, client_secret=client_secret,
                             user_agent=user_agent, check_for_async=False)
        reddit.read_only = True
    except Exception as e:
        logger.error(f"Reddit: could not init official client ({e}) — falling back.")
        return None

    posts_per_query = limits.get("posts_per_query", 12)
    comments_per_post = limits.get("comments_per_post", 4)
    subreddits = limits.get("subreddits") or ["all"]
    max_queries = limits.get("max_queries", 8)
    out, seen = [], set()
    for q in queries[:max_queries]:
        for sub in subreddits:
            try:
                for post in reddit.subreddit(sub).search(q, sort="relevance", time_filter="year", limit=posts_per_query):
                    if post.id in seen:
                        continue
                    seen.add(post.id)
                    body = (getattr(post, "selftext", "") or "")[:800]
                    comment_text = ""
                    try:
                        post.comments.replace_more(limit=0)
                        tops = [c.body for c in post.comments[:comments_per_post] if getattr(c, "body", "")]
                        if tops:
                            comment_text = "\n\nTOP COMMENTS:\n" + "\n".join(f"- {t[:300]}" for t in tops)
                    except Exception:
                        pass
                    created = ""
                    try:
                        created = datetime.fromtimestamp(post.created_utc, tz=timezone.utc).isoformat()
                    except Exception:
                        pass
                    out.append(Result(
                        source="reddit", title=post.title or "",
                        url=f"https://www.reddit.com{post.permalink}",
                        summary=(body[:280] or post.title or ""),
                        raw_snippet=f"[r/{getattr(post.subreddit,'display_name',sub)}] {post.title}\n{body}{comment_text}",
                        timestamp=created,
                    ))
            except Exception as e:
                logger.error(f"Reddit(official): '{q}' in r/{sub}: {e}")
    return out


def fetch(queries, limits, logger):
    # 1) Try the official API (free) first.
    official = _official(queries, limits, logger)
    if official:  # non-empty list
        logger.info(f"Reddit: collected {len(official)} items (official API).")
        return official
    if official is None:
        logger.info("Reddit: no official key — using ScrapingBee fallback.")
    else:
        logger.info("Reddit: official API returned nothing — using ScrapingBee fallback.")

    # 2) Fallback: ScrapingBee on Reddit's search.json.
    if not scrapingbee.available():
        logger.warning("Reddit: no ScrapingBee key either — skipping.")
        return []
    per = limits.get("posts_per_query", 12)
    max_queries = limits.get("max_queries", 8)
    out, seen = [], set()
    for q in queries[:max_queries]:
        for r in scrapingbee.reddit(q, per, logger):
            if r.url in seen:
                continue
            seen.add(r.url)
            out.append(r)
    logger.info(f"Reddit: collected {len(out)} items (via ScrapingBee).")
    return out
