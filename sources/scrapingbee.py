"""
ScrapingBee fallback fetchers for Reddit + Google.

Used ONLY when the free official APIs are unavailable (no Reddit key yet /
Google CSE 403). Uses the SCRAPINGBEE_API_KEY from your existing ScrapingBee
account. Proven-reliable methods: Reddit's own search.json (clean JSON) and
ScrapingBee's Google Search API (structured JSON) — no fragile HTML parsing.
"""
import os
import json
import requests

from .base import Result


def key() -> str:
    return os.getenv("SCRAPINGBEE_API_KEY", "").strip()


def available() -> bool:
    return bool(key())


def google(query, num, logger):
    k = key()
    if not k:
        return []
    try:
        r = requests.get("https://app.scrapingbee.com/api/v1/store/google",
                         params={"api_key": k, "search": query, "country_code": "us"}, timeout=60)
        if r.status_code != 200:
            logger.warning(f"ScrapingBee/Google '{query}': HTTP {r.status_code}")
            return []
        data = r.json()
        out = []
        for o in (data.get("organic_results") or [])[:num]:
            url = o.get("url", "")
            if not url:
                continue
            snip = o.get("description") or o.get("snippet") or ""
            out.append(Result(source="google", title=o.get("title", ""), url=url,
                              summary=snip, raw_snippet=f"QUERY: {query}\n{snip}", timestamp=""))
        return out
    except Exception as e:
        logger.error(f"ScrapingBee/Google '{query}': {e}")
        return []


def reddit(query, limit, logger):
    k = key()
    if not k:
        return []
    rurl = (f"https://www.reddit.com/search.json?q={requests.utils.quote(query)}"
            f"&sort=relevance&t=year&limit={limit}&type=link")
    try:
        r = requests.get("https://app.scrapingbee.com/api/v1/",
                         params={"api_key": k, "url": rurl, "premium_proxy": "true", "render_js": "false"},
                         timeout=120)
        if r.status_code != 200:
            logger.warning(f"ScrapingBee/Reddit '{query}': HTTP {r.status_code}")
            return []
        data = json.loads(r.text)
        out = []
        for c in data.get("data", {}).get("children", [])[:limit]:
            d = c.get("data", {})
            body = (d.get("selftext") or "")[:800]
            out.append(Result(
                source="reddit",
                title=d.get("title", ""),
                url="https://www.reddit.com" + d.get("permalink", ""),
                summary=(body[:280] or d.get("title", "")),
                raw_snippet=f"[r/{d.get('subreddit','')}] {d.get('title','')}\n{body}",
                timestamp="",
            ))
        return out
    except Exception as e:
        logger.error(f"ScrapingBee/Reddit '{query}': {e}")
        return []


def health(logger=None):
    """Quick account check — returns (ok, detail)."""
    k = key()
    if not k:
        return False, "no key"
    try:
        r = requests.get("https://app.scrapingbee.com/api/v1/usage", params={"api_key": k}, timeout=20)
        if r.status_code == 200:
            d = r.json()
            left = d.get("max_api_credit", 0) - d.get("used_api_credit", 0)
            return True, f"OK ({left} credits left)"
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)[:40]
