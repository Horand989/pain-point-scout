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

## Full automation — daily, hands-off, delivered to you

Goal: it runs **every day on its own** and sends you the 5–10 things to reply to
(with drafts) via **Telegram + email**, and drops build-signals into Veto+ — with
no action from you. Command it runs: `python main.py --push-to-veto --notify`.

### A) Delivery setup (one time)
**Telegram (phone):**
1. In Telegram, message **@BotFather** → `/newbot` → follow prompts → copy the **bot token**.
2. Message your new bot once (say "hi").
3. Open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser → find `"chat":{"id": ...}` → that number is your **chat id**.
4. Put both in `.env` (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`).

**Email (Gmail):**
1. Turn on 2-step verification on your Google account.
2. Google Account → Security → **App passwords** → create one → copy the 16-char password.
3. Put your Gmail + that app password into `.env` (`SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_TO`).

Test delivery locally: `python main.py --notify --sources perplexity`

### B) Cloud schedule (runs even when your laptop is off) — GitHub Actions
The workflow is already in `.github/workflows/daily.yml`.
1. Create a **private GitHub repo** and push this project to it.
2. In the repo: **Settings → Secrets and variables → Actions → New repository secret**, and add each key
   (same names as in `.env`): `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`,
   `GOOGLE_API_KEY`, `GOOGLE_CSE_ID`, `PERPLEXITY_API_KEY`, `OPENAI_API_KEY`,
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
   `SMTP_PASSWORD`, `EMAIL_FROM`, `EMAIL_TO`, `VETO_SUPABASE_URL`,
   `VETO_SUPABASE_SERVICE_ROLE_KEY`, `VETO_USER_ID`.
3. Edit the `cron:` time in `daily.yml` if you want (it's in UTC; `0 12 * * *` ≈ 8 AM Eastern).
4. Test it now: repo → **Actions** tab → "Daily Pain Point Scout" → **Run workflow**.

That's it — from then on it runs daily on GitHub's servers and messages you. Your laptop can be off.

### Local alternative (laptop must be on) — Windows Task Scheduler
1. Task Scheduler → Create Basic Task → Daily → pick a time.
2. Action → Start a program:
   - Program: `C:\Users\serfi\Documents\Projects\pain-point-scout\.venv\Scripts\python.exe`
   - Arguments: `main.py --push-to-veto --notify`
   - Start in: `C:\Users\serfi\Documents\Projects\pain-point-scout`

Or keep a window open: `python main.py --schedule --at 08:00 --push-to-veto --notify`

---

## Configuration
Edit `config.py` to change the **topics/niches**, the **search phrasings**, the
**per-source limits**, or the **top-N** size. No secrets live there — keys stay in `.env`.

## Build order (as specced)
Reddit → Google + Perplexity → Quora → scoring → responder → `main.py` wiring → schedule.
Each source module is independently testable; scoring/responder are tested against
`tests/sample_results.py` with no live calls.
