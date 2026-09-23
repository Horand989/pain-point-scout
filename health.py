"""
Source health check — tests each source's credentials/reachability BEFORE the run
so a run can NEVER come back as a silent zero. The result is put in every digest,
so if a source is down you are told exactly which one and why.
"""
import os
import requests


def check_sources():
    """Return a list of (source_name, status_string). status starts with OK or FAIL."""
    out = []

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

    # Google Custom Search
    gk, cx = os.getenv("GOOGLE_API_KEY"), os.getenv("GOOGLE_CSE_ID")
    if not (gk and cx):
        out.append(("Google", "FAIL — missing key or engine id"))
    else:
        try:
            r = requests.get("https://www.googleapis.com/customsearch/v1",
                             params={"key": gk, "cx": cx, "q": "test", "num": 1}, timeout=20)
            if r.status_code == 200:
                out.append(("Google", "OK"))
            elif r.status_code == 403:
                out.append(("Google", "FAIL — HTTP 403 (Custom Search API not active on the project)"))
            else:
                out.append(("Google", f"FAIL — HTTP {r.status_code}"))
        except Exception as e:
            out.append(("Google", f"FAIL — {str(e)[:50]}"))

    # Reddit (official API)
    rc = os.getenv("REDDIT_CLIENT_ID")
    out.append(("Reddit", "OK — credentials present" if rc else "FAIL — no key yet (access pending approval)"))

    # Hacker News (keyless backup — should basically always work)
    try:
        r = requests.get("https://hn.algolia.com/api/v1/search",
                         params={"query": "test", "hitsPerPage": 1}, timeout=15)
        out.append(("HackerNews", "OK" if r.status_code == 200 else f"FAIL — HTTP {r.status_code}"))
    except Exception as e:
        out.append(("HackerNews", f"FAIL — {str(e)[:50]}"))

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
