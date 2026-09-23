"""
Hacker News source — Algolia search API. FREE, no key, keyless backup.

This is the safety net: it needs no credentials, so even if every paid API
(Perplexity, Google, Reddit) is down or unkeyed, this still returns results.
Great for startup / founder / tech / business topics.
"""
import requests

from .base import Result


def fetch(queries, limits, logger):
    out = []
    per = limits.get("results_per_query", 6)
    max_queries = limits.get("max_queries", 10)
    for q in queries[:max_queries]:
        try:
            r = requests.get("https://hn.algolia.com/api/v1/search",
                             params={"query": q, "tags": "story", "hitsPerPage": per}, timeout=15)
            if r.status_code != 200:
                logger.warning(f"HackerNews: '{q}' returned HTTP {r.status_code}")
                continue
            for h in r.json().get("hits", [])[:per]:
                title = h.get("title") or h.get("story_title") or ""
                if not title:
                    continue
                url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
                body = (h.get("story_text") or title)
                out.append(Result(
                    source="hackernews",
                    title=title,
                    url=url,
                    summary=body[:300],
                    raw_snippet=f"QUERY: {q}\n{body[:800]}",
                    timestamp=(h.get("created_at") or "")[:10],
                ))
        except Exception as e:
            logger.error(f"HackerNews: '{q}' failed: {e}")
    logger.info(f"HackerNews: collected {len(out)} items.")
    return out
