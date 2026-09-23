"""
Google source — official Custom Search API as PRIMARY, ScrapingBee as FALLBACK.

Tries the free CSE first. The moment it 403s (API not active on the project),
it stops hammering CSE and switches to ScrapingBee's Google Search API
(structured JSON) — so Google results come through either way.
Never crashes the run.
"""
import os
import requests

from .base import Result
from . import scrapingbee

ENDPOINT = "https://www.googleapis.com/customsearch/v1"


def fetch(queries, limits, logger):
    api_key = os.getenv("GOOGLE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")
    per = limits.get("results_per_query", 5)
    max_queries = limits.get("max_queries", 8)

    out = []
    used_cse = False
    cse_dead = not (api_key and cse_id)

    # 1) Official CSE first (free). Bail to fallback on the first failure.
    if not cse_dead:
        for q in queries[:max_queries]:
            try:
                r = requests.get(ENDPOINT,
                                 params={"key": api_key, "cx": cse_id, "q": q, "num": min(per, 10)},
                                 timeout=20)
                if r.status_code != 200:
                    logger.warning(f"Google CSE '{q}': HTTP {r.status_code} — switching to ScrapingBee fallback.")
                    cse_dead = True
                    break
                used_cse = True
                for item in (r.json().get("items") or [])[:per]:
                    out.append(Result(source="google", title=item.get("title", ""),
                                      url=item.get("link", ""), summary=item.get("snippet", ""),
                                      raw_snippet=f"QUERY: {q}\n{item.get('snippet','')}", timestamp=""))
            except Exception as e:
                logger.error(f"Google CSE '{q}': {e} — switching to ScrapingBee fallback.")
                cse_dead = True
                break

    # 2) Fallback: ScrapingBee Google Search API.
    if (cse_dead or not out) and scrapingbee.available():
        logger.info("Google: using ScrapingBee fallback.")
        seen = {r.url for r in out}
        for q in queries[:max_queries]:
            for r in scrapingbee.google(q, per, logger):
                if r.url in seen:
                    continue
                seen.add(r.url)
                out.append(r)

    via = "CSE" if used_cse and out else ("ScrapingBee" if out else "none")
    logger.info(f"Google: collected {len(out)} items (via {via}).")
    return out
