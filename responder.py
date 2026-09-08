"""
Responder — drafts a rough reply for each Type A top-N item.

The person always reads, edits, and posts manually. This NEVER auto-posts.
If no OPENAI_API_KEY is set (or --dry-run), it falls back to a helpful template
so the whole pipeline still runs and can be tested offline.
"""
import os

from config import RESPONDER_MODEL

SYSTEM = (
    "You are helping a busy solo founder reply, by hand, to a real online post. "
    "Write a SHORT (3-6 sentence) reply that is genuinely helpful and human. "
    "Acknowledge their situation, give one or two concrete, useful pointers, and be warm. "
    "Absolutely no sales pitch, no links, no self-promotion, no 'DM me'. "
    "Sound like a real person who has been there, not a brand. Plain text only."
)


def _prompt(r) -> str:
    return (
        f"SOURCE: {r.source}\n"
        f"POST TITLE: {r.title}\n"
        f"CONTEXT: {r.raw_snippet[:1200]}\n\n"
        "Write the rough draft reply now."
    )


def _template(r) -> str:
    return (
        f"[TEMPLATE DRAFT — add your OpenAI key for AI drafts]\n"
        f"Re: \"{r.title[:80]}\" — acknowledge their situation in one line, share one "
        f"concrete thing that helped you with this, and ask a short follow-up question. "
        f"Keep it human and non-salesy."
    )


def draft_responses(items, logger, dry_run=False):
    api_key = os.getenv("OPENAI_API_KEY")

    if dry_run or not api_key:
        if not api_key and not dry_run:
            logger.warning("Responder: OPENAI_API_KEY not set — using template drafts.")
        for r in items:
            r.draft_response = _template(r)
        return items

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
    except Exception as e:
        logger.error(f"Responder: could not init OpenAI ({e}) — using template drafts.")
        for r in items:
            r.draft_response = _template(r)
        return items

    for r in items:
        try:
            resp = client.chat.completions.create(
                model=RESPONDER_MODEL,
                messages=[{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": _prompt(r)}],
            )
            r.draft_response = (resp.choices[0].message.content or "").strip() or _template(r)
        except Exception as e:
            logger.error(f"Responder: draft failed for {r.url}: {e}")
            r.draft_response = _template(r)

    logger.info(f"Responder: drafted {len(items)} replies.")
    return items
