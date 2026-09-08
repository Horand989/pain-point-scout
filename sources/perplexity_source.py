"""
Perplexity source — sonar API.

Surfaces additional real questions/discussions and the framing people use
around the niches. Best-effort JSON parsing (models sometimes wrap output).
Never crashes the run: logs and continues on any error.
"""
import os
import re
import json
import requests

from .base import Result

ENDPOINT = "https://api.perplexity.ai/chat/completions"

SYSTEM = (
    "You surface REAL, recent online questions and discussions that real people are having. "
    "Do not invent sources. Return ONLY JSON of the form "
    '{"items":[{"title":"...","url":"...","snippet":"..."}]} and nothing else.'
)


def _parse_items(content: str):
    """Best-effort extraction of the items array from the model's reply."""
    if not content:
        return []
    # strip code fences
    content = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.MULTILINE).strip()
    try:
        obj = json.loads(content)
        if isinstance(obj, dict):
            return obj.get("items", []) or []
        if isinstance(obj, list):
            return obj
    except Exception:
        # try to find the first {...} block
        m = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(0))
                return obj.get("items", []) if isinstance(obj, dict) else []
            except Exception:
                return []
    return []


def fetch(queries, limits, logger):
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        logger.warning("Perplexity: PERPLEXITY_API_KEY not set — skipping this source.")
        return []

    model = os.getenv("PERPLEXITY_MODEL", "sonar")
    results_per_query = limits.get("results_per_query", 5)
    max_queries = limits.get("max_queries", 12)

    out = []
    for q in queries[:max_queries]:
        try:
            resp = requests.post(
                ENDPOINT,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM},
                        {"role": "user", "content": (
                            f"Find {results_per_query} recent, real questions or discussions about: \"{q}\". "
                            "Focus on pain points, complaints, and unmet needs. JSON only."
                        )},
                    ],
                },
                timeout=40,
            )
            if resp.status_code != 200:
                logger.warning(f"Perplexity: '{q}' returned HTTP {resp.status_code}: {resp.text[:200]}")
                continue
            content = resp.json()["choices"][0]["message"]["content"]
            for item in _parse_items(content)[:results_per_query]:
                if not isinstance(item, dict):
                    continue
                out.append(Result(
                    source="perplexity",
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    summary=item.get("snippet", ""),
                    raw_snippet=f"QUERY: {q}\n{item.get('snippet', '')}",
                    timestamp="",
                ))
        except Exception as e:
            logger.error(f"Perplexity: query failed for '{q}': {e}")
            continue

    logger.info(f"Perplexity: collected {len(out)} items.")
    return out
