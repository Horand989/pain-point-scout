"""
Quora source — public pages only, no login, no official API.

Checks robots.txt before fetching, keeps request volume low and spaced out,
and degrades gracefully (Quora is JS-heavy and often blocks server requests —
that is EXPECTED; we log it and return whatever we get rather than crashing).
"""
import time
import urllib.robotparser
from urllib.parse import quote_plus

import requests

from .base import Result

UA = "Mozilla/5.0 (compatible; pain-point-scout/0.1; +research; contact via Reddit)"


def _robots_allows(url, logger) -> bool:
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url("https://www.quora.com/robots.txt")
    try:
        rp.read()
    except Exception as e:
        logger.warning(f"Quora: could not read robots.txt ({e}) — skipping to stay safe.")
        return False
    try:
        return rp.can_fetch(UA, url)
    except Exception:
        return False


def fetch(queries, limits, logger):
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("Quora: beautifulsoup4 not installed — skipping.")
        return []

    delay = limits.get("request_delay_seconds", 8)
    max_requests = limits.get("max_requests", 8)
    per_query = limits.get("results_per_query", 10)

    out = []
    requests_made = 0

    for q in queries:
        if requests_made >= max_requests:
            logger.warning(f"Quora: reached max_requests ({max_requests}) — stopping (staying polite).")
            break

        search_url = f"https://www.quora.com/search?q={quote_plus(q)}&type=question"

        if not _robots_allows(search_url, logger):
            logger.warning(f"Quora: robots.txt disallows or blocks '{search_url}' — skipping this query.")
            continue

        try:
            time.sleep(delay)  # spaced out — no official API
            resp = requests.get(search_url, headers={"User-Agent": UA}, timeout=25)
            requests_made += 1

            if resp.status_code != 200:
                logger.warning(f"Quora: '{q}' returned HTTP {resp.status_code} — skipping.")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            found = 0
            seen = set()
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True)
                # public question pages look like https://www.quora.com/Some-Question
                if (
                    href.startswith("https://www.quora.com/")
                    and "?" not in href
                    and "/topic/" not in href
                    and "/profile/" not in href
                    and len(text) > 15
                    and href not in seen
                ):
                    seen.add(href)
                    out.append(Result(
                        source="quora",
                        title=text,
                        url=href,
                        summary=text,
                        raw_snippet=f"QUERY: {q}\n{text}",
                        timestamp="",
                    ))
                    found += 1
                    if found >= per_query:
                        break
        except Exception as e:
            logger.error(f"Quora: query failed for '{q}': {e}")
            continue

    if not out:
        logger.info(
            "Quora: 0 items. This is common — Quora renders results via JavaScript and "
            "often blocks server-side requests. Logged, not an error."
        )
    else:
        logger.info(f"Quora: collected {len(out)} items across {requests_made} requests.")
    return out
