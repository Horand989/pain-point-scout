"""
Pain Point Scout — daily entry point.

Runs all four sources in sequence, classifies + ranks the results, drafts
replies for the Type A top list, and writes a dated report. Any source that
fails is logged and skipped — the run never crashes as a whole.

Usage:
    python main.py                 # full live run (uses whatever keys are in .env)
    python main.py --dry-run       # no OpenAI calls; template drafts (offline-friendly)
    python main.py --sources reddit google   # only run specific sources
    python main.py --schedule      # run once now, then daily via APScheduler
"""
import os
import sys
import argparse
import logging
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv

# Use the OS certificate store so corporate/antivirus SSL interception on this
# machine does not break HTTPS calls (fixes the "self-signed certificate" errors).
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import config
import health
from sources import reddit_source, quora_source, google_source, perplexity_source, hackernews_source
from scoring import classify_and_score
from responder import draft_responses
import bridge_veto
import notify
import fb_posts

SOURCE_FUNCS = {
    "hackernews": (hackernews_source.fetch, "hackernews"),  # keyless backup — always try it
    "perplexity": (perplexity_source.fetch, "perplexity"),
    "reddit": (reddit_source.fetch, "reddit"),
    "google": (google_source.fetch, "google"),
    "quora": (quora_source.fetch, "quora"),
}


def setup_logger(run_date: str) -> logging.Logger:
    os.makedirs(config.LOGS_DIR, exist_ok=True)
    logger = logging.getLogger("scout")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s")
    fh = logging.FileHandler(os.path.join(config.LOGS_DIR, f"{run_date}_run.log"), encoding="utf-8")
    fh.setFormatter(fmt)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


def run_once(selected_sources=None, dry_run=False, push_to_veto=False, notify_me=False):
    run_date = datetime.now().strftime("%Y-%m-%d")
    logger = setup_logger(run_date)
    logger.info("=" * 60)
    logger.info(f"Pain Point Scout — daily run {run_date}")

    queries = config.build_search_queries()
    logger.info(f"Built {len(queries)} search queries across {len(config.TOPICS_AND_NICHES)} niches.")

    active = selected_sources or list(SOURCE_FUNCS.keys())

    # Health check up front — so a zero is NEVER a mystery: we know which
    # source is up or down (and why) before we even run, and it goes in the digest.
    source_status = health.check_sources()
    logger.info("--- Source health ---")
    for n, s in source_status:
        logger.info(f"   {n}: {s}")

    # Sources the health check already knows are down — skip them so we don't
    # waste time hammering a dead API (their failure is already flagged in the digest).
    down = {n.lower() for n, s in source_status if s.startswith("FAIL")}

    all_results = []
    source_counts = {}
    for name in active:
        if name in down:
            logger.info(f"--- Source: {name} — SKIPPED (health check: DOWN) ---")
            source_counts[name] = 0
            continue
        fetch_fn, _ = SOURCE_FUNCS[name]
        limits = config.LIMITS.get(name, {})
        logger.info(f"--- Source: {name} ---")
        try:
            items = fetch_fn(queries, limits, logger) or []
            all_results.extend(items)
            source_counts[name] = len(items)
        except Exception as e:
            source_counts[name] = 0
            logger.error(f"{name}: source crashed unexpectedly ({e}) — skipped.")

    logger.info(f"Collected {len(all_results)} raw items total.")
    if not all_results:
        logger.warning("NO RESULTS from any source — see Source health above. This is NOT normal: "
                       "a source is down. The digest will flag which one and why.")

    top_a, all_a, type_b = classify_and_score(all_results, logger)
    draft_responses(top_a, logger, dry_run=dry_run)

    # Tailored Facebook post ideas (rotate a few groups/day; posted BY HAND).
    logger.info("--- Facebook post ideas ---")
    fb = fb_posts.generate_group_posts(top_a, logger, dry_run=dry_run)

    _write_reports(run_date, top_a, type_b, fb, source_status, source_counts, logger)

    # Optional bridge: push build-signals into Veto+ (writes only to its DB).
    if push_to_veto:
        logger.info("--- Bridge to Veto+ ---")
        bridge_veto.push_build_signals(type_b, logger, dry_run=dry_run)

    # Optional delivery: Telegram + email (each fires only if configured).
    if notify_me:
        logger.info("--- Delivery ---")
        md_path = os.path.join(config.DATA_DIR, f"{run_date}_report.md")
        notify.deliver(run_date, top_a, type_b, logger, md_path=md_path, fb=fb,
                       source_status=source_status, source_counts=source_counts)

    logger.info("Run complete.")
    logger.info("=" * 60)
    return top_a, type_b


def _write_reports(run_date, top_a, type_b, fb, source_status, source_counts, logger):
    os.makedirs(config.DATA_DIR, exist_ok=True)

    # Type A top list — the daily action list, as CSV.
    a_rows = [{
        "rank": r.rank, "score": r.score, "source": r.source,
        "title": r.title, "url": r.url, "summary": r.summary,
        "draft_response": r.draft_response,
    } for r in top_a]
    a_path = os.path.join(config.DATA_DIR, f"{run_date}_typeA_top10.csv")
    pd.DataFrame(a_rows).to_csv(a_path, index=False)

    # Type B build signals — kept separate, never folded into the top 10.
    b_rows = [{
        "source": r.source, "pattern": r.pattern or r.title,
        "title": r.title, "url": r.url, "detail": r.summary,
    } for r in type_b]
    b_path = os.path.join(config.DATA_DIR, f"{run_date}_typeB_signals.csv")
    pd.DataFrame(b_rows).to_csv(b_path, index=False)

    # Human-readable daily report — the "open one thing each morning" file.
    md_path = os.path.join(config.DATA_DIR, f"{run_date}_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Pain Point Scout — {run_date}\n\n")
        f.write(f"**{len(top_a)} engagement opportunities** to reply to today, "
                f"plus **{len(type_b)} build signals** to consider.\n\n")
        f.write("## Source status\n\n")
        for name, st in source_status:
            key = {"HackerNews": "hackernews"}.get(name, name.lower())
            got = f" — {source_counts.get(key, 0)} found" if st.startswith("OK") else ""
            f.write(f"- **{name}:** {st}{got}\n")
        f.write("\n")
        if not top_a and not type_b:
            f.write("> WARNING: No conversations found. See Source status above — a source is DOWN "
                    "(usually a dead or missing API key). This is not normal; fix the flagged source.\n\n")
        f.write("---\n\n## ✍️ Today's Top Engagement Opportunities (Type A)\n\n")
        if not top_a:
            f.write("_No engagement opportunities found today._\n\n")
        for r in top_a:
            f.write(f"### {r.rank}. [{r.source}] {r.title}\n")
            f.write(f"- **Link:** {r.url}\n")
            f.write(f"- **Why it ranked ({r.score}/100):** {r.summary[:200]}\n")
            f.write(f"- **Draft reply:**\n\n  > {r.draft_response.strip().replace(chr(10), chr(10)+'  > ')}\n\n")
        f.write("---\n\n## 💡 Build Signals (Type B) — possible ideas for the validator\n\n")
        if not type_b:
            f.write("_No build signals found today._\n\n")
        for r in type_b[:25]:
            f.write(f"- **[{r.source}]** _{r.pattern or r.title}_ — {r.url}\n")
        f.write("\n---\n\n## Facebook post ideas (rotate; post BY HAND)\n\n")
        if not fb:
            f.write("_No Facebook post ideas today._\n")
        for item in (fb or []):
            f.write(f"### {item.get('group','')}\n{item.get('post','')}\n\n")

    logger.info(f"Wrote: {a_path}")
    logger.info(f"Wrote: {b_path}")
    logger.info(f"Wrote: {md_path}  <-- open this each morning")


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Pain Point Scout — daily discovery + drafts.")
    parser.add_argument("--dry-run", action="store_true", help="No OpenAI calls; template drafts.")
    parser.add_argument("--sources", nargs="+", choices=list(SOURCE_FUNCS.keys()),
                        help="Only run these sources (default: all four).")
    parser.add_argument("--schedule", action="store_true", help="Run now, then daily via APScheduler.")
    parser.add_argument("--at", default="08:00", help="Daily run time HH:MM for --schedule (default 08:00).")
    parser.add_argument("--push-to-veto", action="store_true",
                        help="Push Type B build-signals into Veto+ as pending ideas (needs VETO_* in .env).")
    parser.add_argument("--notify", action="store_true",
                        help="Send the daily digest via Telegram and/or email (needs their creds in .env).")
    args = parser.parse_args()

    run_once(selected_sources=args.sources, dry_run=args.dry_run,
             push_to_veto=args.push_to_veto, notify_me=args.notify)

    if args.schedule:
        try:
            from apscheduler.schedulers.blocking import BlockingScheduler
        except ImportError:
            print("APScheduler not installed. Use Windows Task Scheduler instead (see README).")
            return
        hh, mm = (int(x) for x in args.at.split(":"))
        sched = BlockingScheduler()
        sched.add_job(lambda: run_once(selected_sources=args.sources, dry_run=args.dry_run,
                                       push_to_veto=args.push_to_veto, notify_me=args.notify),
                      "cron", hour=hh, minute=mm)
        print(f"Scheduled daily run at {args.at}. Leave this window open. Ctrl+C to stop.")
        try:
            sched.start()
        except (KeyboardInterrupt, SystemExit):
            pass


if __name__ == "__main__":
    main()
