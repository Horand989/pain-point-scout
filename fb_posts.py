"""
Facebook post generator — one DISTINCT, human, tailored post per group.

Built from the day's REAL pain points (what the Scout actually found), then framed
for each group's audience/region/angle/tone. Posts are drafts to edit and post BY
HAND. No competitor promotion, no product pitch, no AI tells, no dashes.
Falls back to simple templates if no OpenAI key (or --dry-run).
"""
import os
import re
import json
import datetime

from config import RESPONDER_MODEL
from facebook_groups import groups_for_today

SYSTEM = (
    "You write short, genuine Facebook posts for a solo business owner to post BY HAND in "
    "communities he belongs to. Each post starts a real conversation and gives value first. "
    "STRICT RULES: sound like a real human, never like AI or marketing. Do NOT pitch or mention "
    "any product (his own or competitors like Zapier). No links, no 'DM me', no hashtags. "
    "Ask one genuine question so members reply. Keep it 2-4 sentences. Do NOT use dashes of any "
    "kind (— or -); use commas or periods. Tailor each post to that group's audience, region, "
    "angle and tone, and make every post clearly DIFFERENT from the others."
)


def _pains_blurb(top_items) -> str:
    lines = []
    for r in (top_items or [])[:6]:
        t = getattr(r, "title", "") or ""
        s = getattr(r, "summary", "") or ""
        lines.append(f"- {t} :: {s}"[:240])
    return "\n".join(lines) if lines else "(no strong pain points found today; use general small-business struggles)"


def _template(group, pains_blurb) -> str:
    return (f"[TEMPLATE - add OpenAI key for tailored posts] Post for {group['name']} "
            f"({group['audience']}): ask this group about their biggest current struggle, "
            f"framed around {group['angle']}, in a {group['tone']} voice. Lead with value, "
            f"end with a genuine question.")


def generate_group_posts(top_items, logger, dry_run=False, day_index=None):
    if day_index is None:
        day_index = datetime.date.today().toordinal()
    groups = groups_for_today(day_index)
    if not groups:
        return []

    pains = _pains_blurb(top_items)
    api_key = os.getenv("OPENAI_API_KEY")

    if dry_run or not api_key:
        if not api_key and not dry_run:
            logger.warning("FB posts: no OPENAI_API_KEY - using templates.")
        return [{"group": g["name"], "post": _template(g, pains)} for g in groups]

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        group_desc = "\n".join(
            f'{i+1}. "{g["name"]}" | audience: {g["audience"]} | region: {g["region"]} '
            f'| angle: {g["angle"]} | tone: {g["tone"]}'
            for i, g in enumerate(groups)
        )
        user = (
            f"Today's REAL pain points people voiced online:\n{pains}\n\n"
            f"Write ONE Facebook post for EACH of these {len(groups)} groups, each distinct and "
            f"tailored to its audience/region/angle/tone:\n{group_desc}\n\n"
            'Return ONLY JSON: {"posts":[{"group":"exact group name","post":"the post text"}]}'
        )
        resp = client.chat.completions.create(
            model=RESPONDER_MODEL,
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
        posts = data.get("posts", []) if isinstance(data, dict) else []
        # strip any stray dashes the model slips in
        cleaned = []
        for p in posts:
            if isinstance(p, dict) and p.get("post"):
                text = re.sub(r"\s*[—–―]\s*", ", ", p["post"])
                text = re.sub(r"\s-\s", ", ", text).strip()
                cleaned.append({"group": p.get("group", ""), "post": text})
        if cleaned:
            logger.info(f"FB posts: generated {len(cleaned)} tailored posts.")
            return cleaned
    except Exception as e:
        logger.error(f"FB posts: generation failed ({e}) - using templates.")

    return [{"group": g["name"], "post": _template(g, pains)} for g in groups]
