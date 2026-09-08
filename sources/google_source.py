"""
Google source — official Custom Search JSON API.

We do NOT scrape Google's results pages directly (against ToS + unreliable).
Surfaces the questions people type into Google around the niches.
Never crashes the run: logs and continues on any error.
"""
import os
import requests

from .base import Result

ENDPOINT = "https://www.googleapis.com/customsearch/v1"


def fetch(queries, limits, logger):
    api_key = os.getenv("GOOGLE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")

    if not api_key or not cse_id:
        logger.warning("Google: GOOGLE_API_KEY/GOOGLE_CSE_ID not set — skipping this source.")
        return []

    results_per_query = limits.get("results_per_query", 5)
    daily_cap = limits.get("daily_query_cap", 90)

    out = []
    used = 0

    for q in queries:
        if used >= daily_cap:
            logger.warning(f"Google: hit daily query cap ({daily_cap}) — stopping.")
            break
        try:
            resp = requests.get(
                ENDPOINT,
                params={"key": api_key, "cx": cse_id, "q": q, "num": min(results_per_query, 10)},
                timeout=20,
            )
            used += 1
            if resp.status_code != 200:
                logger.warning(f"Google: '{q}' returned HTTP {resp.status_code}: {resp.text[:200]}")
                continue
            data = resp.json()
            for item in (data.get("items") or [])[:results_per_query]:
                out.append(Result(
                    source="google",
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    summary=item.get("snippet", ""),
                    raw_snippet=f"QUERY: {q}\n{item.get('snippet', '')}",
                    timestamp="",
                ))
        except Exception as e:
            logger.error(f"Google: search failed for '{q}': {e}")
            continue

    logger.info(f"Google: collected {len(out)} items across {used} queries.")
    return out
