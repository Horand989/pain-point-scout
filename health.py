"""
Source health check — tests each source's credentials/reachability BEFORE the run
so a run can NEVER come back as a silent zero. The result is put in every digest,
so if a source is down you are told exactly which one and why.
"""
import os
import requests

from sources import scrapingbee


def check_sources():
    """Return a list of (source_name, status_string). status starts with OK or FAIL."""
    out = []
    sb_up = scrapingbee.available()

    # Perplexity
    k = os.getenv("PERPLEXITY_API_KEY")
    if not k:
        out.append(("Perplexity", "FAIL — no API key set"))
    else:
        try:
            r = requests.post("https://api.perplexity.ai/chat/completions",
                              headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json"},
                              json={"model": "sonar", "messages": [{"role": "user", "content": "hi"}]},
                              timeout=20)
            if r.status_code == 200:
                out.append(("Perplexity", "OK"))
            elif r.status_code == 401:
                out.append(("Perplexity", "FAIL — HTTP 401 (dead/invalid API key, update it)"))
            else:
                out.append(("Perplexity", f"FAIL — HTTP {r.status_code}"))
        except Exception as e:
            out.append(("Perplexity", f"FAIL — {str(e)[:50]}"))

    # Google Custom Search (official). If it's down but ScrapingBee is available,
    # report OK — via ScrapingBee, so the run still fetches Google results.
    gk, cx = os.getenv("GOOGLE_API_KEY"), os.getenv("GOOGLE_CSE_ID")
    google_status = None
    if not (gk and cx):
        google_status = "missing key or engine id"
    else:
        try:
            r = requests.get("https://www.googleapis.com/customsearch/v1",
                             params={"key": gk, "cx": cx, "q": "test", "num": 1}, timeout=20)
            if r.status_code == 200:
                out.append(("Google", "OK"))
            elif r.status_code == 403:
                google_status = "HTTP 403 (Custom Search API not active on the project)"
            else:
                google_status = f"HTTP {r.status_code}"
        except Exception as e:
            google_status = str(e)[:50]
    if google_status is not None:
        if sb_up:
            out.append(("Google", f"OK — via ScrapingBee (official CSE: {google_status})"))
        else:
            out.append(("Google", f"FAIL — {google_status}; no ScrapingBee key for fallback"))

    # Reddit (official API). Same fallback logic: no official key but ScrapingBee up = OK.
    rc = os.getenv("REDDIT_CLIENT_ID")
    if rc:
        out.append(("Reddit", "OK — credentials present"))
    elif sb_up:
        out.append(("Reddit", "OK — via ScrapingBee (no official key yet)"))
    else:
        out.append(("Reddit", "FAIL — no key yet (access pending approval); no ScrapingBee key for fallback"))

    # Hacker News (keyless backup — should basically always work)
    try:
        r = requests.get("https://hn.algolia.com/api/v1/search",
                         params={"query": "test", "hitsPerPage": 1}, timeout=15)
        out.append(("HackerNews", "OK" if r.status_code == 200 else f"FAIL — HTTP {r.status_code}"))
    except Exception as e:
        out.append(("HackerNews", f"FAIL — {str(e)[:50]}"))

    # ScrapingBee (the fallback engine for Reddit + Google) — report separately.
    if sb_up:
        ok, detail = scrapingbee.health()
        out.append(("ScrapingBee", f"OK — {detail}" if ok else f"FAIL — {detail}"))
    else:
        out.append(("ScrapingBee", "FAIL — no API key set (Reddit/Google have no fallback)"))

    return out


def format_status(status, counts=None):
    """Human-readable status block for the digest. counts = {source: n_items}."""
    lines = ["— Source status —"]
    for name, st in status:
        mark = "OK" if st.startswith("OK") else "DOWN"
        got = ""
        if counts is not None:
            key = {"HackerNews": "hackernews"}.get(name, name.lower())
            if key in counts:
                got = f"  ({counts[key]} found)"
        lines.append(f"[{mark}] {name}: {st}{got}")
    return "\n".join(lines)
