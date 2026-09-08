# Pain Point Scout

A daily tool that finds real online conversations, questions, and pain points
across four sources, ranks the best ones, drafts a rough reply for each, and
hands you a short daily list — so daily outreach takes **minutes, not hours**.

It **never auto-posts anything.** You read, edit, and post every reply yourself.

Standalone tool. It does **not** change ValidatePulse / Veto+ — later, its
"build signals" can be fed into that idea validator by hand.

---

## Sources (only these four)
1. **Reddit** — official API (via `praw`). Most reliable.
2. **Quora** — public pages only, respects `robots.txt`, low + spaced-out volume (no API exists).
3. **Google** — official Custom Search JSON API (not page scraping).
4. **Perplexity** — `sonar` API.

Facebook, LinkedIn, and Instagram are **excluded entirely** by design.

## Two kinds of results
- **Type A — engagement opportunities:** a real post/question you could reply to today. Scored, ranked into a **top 10**, each with a drafted reply.
- **Type B — build signals:** patterns hinting at an unmet need / product idea. Listed **separately** — raw material to later run through your idea validator.

---

## Setup (one time)

```bash
cd Documents/Projects/pain-point-scout
py -m venv .venv
.venv\Scripts\activate            # Windows (PowerShell/CMD)
pip install -r requirements.txt
copy .env.example .env             # then edit .env with your keys
```

### Getting each key (all optional — a missing key just skips that source)
| Source | What you need | Where |
|---|---|---|
| Reddit | client id + secret + user agent | https://www.reddit.com/prefs/apps → create app → type **script** |
| Google | API key + Search-engine ID (cx) | https://developers.google.com/custom-search/v1/introduction and https://programmablesearchengine.google.com (set to search the whole web) |
| Perplexity | API key | You already have this in ValidatePulse |
| OpenAI | API key (for drafting replies) | Your existing OpenAI key |

> **Free-tier note:** Google Custom Search is free for 100 queries/day — the tool caps itself under that.

---

## Run

```bash
# Offline sanity check (no keys, template drafts) — proves the pipeline works:
python tests/test_pipeline.py

# Dry run of the FULL pipeline (real sources you have keys for, template drafts, no OpenAI cost):
python main.py --dry-run

# Full live run (uses whatever keys are in .env):
python main.py

# Only run specific sources:
python main.py --sources reddit google
```

### Output (in `data/`, dated so nothing is overwritten)
- `YYYY-MM-DD_report.md` — **open this each morning.** Top 10 with drafts + build signals.
- `YYYY-MM-DD_typeA_top10.csv` — the action list.
- `YYYY-MM-DD_typeB_signals.csv` — build signals for the validator.
- `logs/YYYY-MM-DD_run.log` — skipped items, unreachable sites, errors.

---

## Daily schedule

**Recommended on Windows — Task Scheduler** (survives reboots, no window to keep open):
1. Open Task Scheduler → Create Basic Task → Daily → pick a time.
2. Action → Start a program:
   - Program: `C:\Users\serfi\Documents\Projects\pain-point-scout\.venv\Scripts\python.exe`
   - Arguments: `main.py`
   - Start in: `C:\Users\serfi\Documents\Projects\pain-point-scout`

**Or, built-in scheduler** (keeps a window open):
```bash
python main.py --schedule --at 08:00
```

---

## Configuration
Edit `config.py` to change the **topics/niches**, the **search phrasings**, the
**per-source limits**, or the **top-N** size. No secrets live there — keys stay in `.env`.

## Build order (as specced)
Reddit → Google + Perplexity → Quora → scoring → responder → `main.py` wiring → schedule.
Each source module is independently testable; scoring/responder are tested against
`tests/sample_results.py` with no live calls.
