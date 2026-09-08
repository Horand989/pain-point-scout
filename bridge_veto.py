"""
Bridge to Veto+ (ValidatePulse).

Pushes the Scout's Type B build-signals into Veto+'s Supabase `research_sessions`
table as 'pending' ideas, so they appear inside Veto+'s existing saved-ideas list,
ready to validate. This writes ONLY to that table via the Supabase REST API — it
changes NOTHING in the Veto+ codebase.

Off unless VETO_SUPABASE_URL + VETO_SUPABASE_SERVICE_ROLE_KEY + VETO_USER_ID are
set AND main.py is run with --push-to-veto. De-duplicates against ideas already
pending for the user so daily runs don't pile up repeats.
"""
import os
import requests


def _cfg():
    return (
        os.getenv("VETO_SUPABASE_URL"),
        os.getenv("VETO_SUPABASE_SERVICE_ROLE_KEY"),
        os.getenv("VETO_USER_ID"),
    )


def available() -> bool:
    url, key, uid = _cfg()
    return bool(url and key and uid)


def _existing_pending_texts(url, key, uid, logger):
    try:
        r = requests.get(
            f"{url}/rest/v1/research_sessions",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            params={"select": "idea_text", "user_id": f"eq.{uid}",
                    "status": "eq.pending", "limit": "500"},
            timeout=20,
        )
        if r.status_code == 200:
            return {(row.get("idea_text") or "").strip().lower() for row in r.json()}
        logger.warning(f"Bridge: dedupe read returned HTTP {r.status_code}; proceeding without dedupe.")
    except Exception as e:
        logger.warning(f"Bridge: could not read existing ideas ({e}); proceeding without dedupe.")
    return set()


def push_build_signals(type_b, logger, limit=8, dry_run=False):
    """Insert up to `limit` new Type B signals into Veto+ as pending ideas."""
    url, key, uid = _cfg()
    if not (url and key and uid):
        logger.info("Bridge: VETO_* env not set — skipping push to Veto+.")
        return 0

    existing = _existing_pending_texts(url, key, uid, logger)
    rows = []
    for r in type_b:
        idea = (r.pattern or r.title or "").strip()
        if not idea or idea.lower() in existing:
            continue
        existing.add(idea.lower())
        rows.append({
            "user_id": uid,
            "idea_text": idea,
            "target_audience": f"Surfaced by Pain Point Scout from {r.source}: {r.title[:180]}",
            "status": "pending",
            "platforms": ["reddit", "x", "google", "perplexity", "quora"],
            "thread_count": 0,
        })
        if len(rows) >= limit:
            break

    if not rows:
        logger.info("Bridge: no new build-signals to push (all duplicates or empty).")
        return 0

    if dry_run:
        logger.info(f"Bridge (dry-run): WOULD push {len(rows)} ideas into Veto+:")
        for row in rows:
            logger.info(f"   - {row['idea_text']}")
        return 0

    try:
        r = requests.post(
            f"{url}/rest/v1/research_sessions",
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Content-Type": "application/json", "Prefer": "return=minimal"},
            json=rows, timeout=30,
        )
        if r.status_code in (200, 201, 204):
            logger.info(f"Bridge: pushed {len(rows)} ideas into Veto+ "
                        f"(they'll appear in the saved-ideas list, status 'pending').")
            return len(rows)
        logger.error(f"Bridge: push failed HTTP {r.status_code}: {r.text[:300]}")
        return 0
    except Exception as e:
        logger.error(f"Bridge: push error: {e}")
        return 0
