"""
Responder — drafts a rough reply for each Type A top-N item.

The person always reads, edits, and posts manually. This NEVER auto-posts.
If no OPENAI_API_KEY is set (or --dry-run), it falls back to a helpful template
so the whole pipeline still runs and can be tested offline.
"""
import os

from config import RESPONDER_MODEL

SYSTEM = (
    "You help a solo business owner reply BY HAND to a SPECIFIC online post. "
    "Write a short reply (3-5 sentences) that sounds like a real, specific human who has "
    "actually done this, not a brand and not an AI.\n"
    "HARD RULES:\n"
    "- NEVER open with generic empathy filler. BANNED openers (do not use these or anything "
    "like them): 'I totally get', 'I totally understand', 'I can relate', 'I completely "
    "understand', 'I feel you', 'I hear you', 'Great question', 'I get where you're coming from'. "
    "Start differently every time, ideally by reacting to the SPECIFIC thing they said.\n"
    "- Engage the actual details of THIS post. No generic advice that could apply to anyone.\n"
    "- Share ONE concrete, real insight or approach from lived experience.\n"
    "- Do NOT name or recommend ANY product or tool (not Zapier, Notion, Buffer, Hootsuite, "
    "Todoist, ChatGPT, Airtable, or any other). Share the principle or approach, never a product.\n"
    "- No sales pitch, no self-promotion, no links, no 'DM me', no hashtags.\n"
    "- Do NOT use dashes of any kind (the long dash or the hyphen as punctuation); use commas "
    "or periods.\n"
    "- End with a short, genuine question that invites them to reply.\n"
    "Plain text only. Sound human and specific."
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

    import re as _re
    for r in items:
        try:
            resp = client.chat.completions.create(
                model=RESPONDER_MODEL,
                messages=[{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": _prompt(r)}],
            )
            text = (resp.choices[0].message.content or "").strip()
            # strip any stray dashes-as-punctuation the model slips in
            text = _re.sub(r"\s*[—–―]\s*", ", ", text)  # em/en dashes anywhere
            text = _re.sub(r"\s-\s", ", ", text)          # spaced hyphen
            r.draft_response = text or _template(r)
        except Exception as e:
            logger.error(f"Responder: draft failed for {r.url}: {e}")
            r.draft_response = _template(r)

    logger.info(f"Responder: drafted {len(items)} replies.")
    return items
