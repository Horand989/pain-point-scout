"""
Central, non-secret configuration for Pain Point Scout.

Topics/niches, the search phrasings, per-source request limits, and output
settings live here so nothing is hardcoded inside the source modules.
API keys live in .env (loaded by python-dotenv), never here.
"""
import os

# ── Topics & niches — applied consistently across ALL four sources ───────────
TOPICS_AND_NICHES = [
    "solo entrepreneurs",
    "founders",
    "new startups",
    "small business owners",
    "AI tools",
    "AI tool discovery",
    "automation for small business",
    "affiliate marketing",
]

# Intent phrasings that turn a niche into things people actually type/ask.
# Used to build the search-query batch for Google, Perplexity, Reddit, Quora.
INTENT_TEMPLATES = [
    "{t}",
    "best AI tool for {t}",
    "how do I automate {t}",
    "{t} struggling with",
    "{t} what tool should I use",
    "{t} recommendations",
]


def build_search_queries():
    """Expand the topics/niches into a de-duplicated batch of search queries."""
    queries = []
    for t in TOPICS_AND_NICHES:
        for tmpl in INTENT_TEMPLATES:
            q = tmpl.format(t=t).strip()
            if q and q not in queries:
                queries.append(q)
    return queries


# ── Per-source request limits (conservative by default) ──────────────────────
# Reddit: official API, generous — but stay reasonable.
# Google: free Custom Search tier is 100 queries/day; stay under it.
# Quora: NO official API — keep volume very low and spaced out.
# Perplexity: metered API — modest.
LIMITS = {
    "reddit": {
        "posts_per_query": 12,
        "comments_per_post": 4,
        # Search across all of Reddit plus a few high-signal subs.
        "subreddits": [
            "all", "Entrepreneur", "smallbusiness", "startups",
            "SaaS", "artificial", "AItools", "Affiliatemarketing",
        ],
        "max_queries": 8,  # don't run every template against every sub
    },
    "google": {
        "results_per_query": 5,
        "daily_query_cap": 90,   # stay under the free 100/day
    },
    "perplexity": {
        "results_per_query": 5,
        "max_queries": 12,
    },
    "quora": {
        "results_per_query": 10,
        "request_delay_seconds": 8,  # spaced out — Quora has no API
        "max_requests": 8,
    },
}

# ── Output / ranking ─────────────────────────────────────────────────────────
TOP_N = 10                       # size of the daily Type A list
DATA_DIR = "data"
LOGS_DIR = "logs"

# ── Models (read from .env, with safe defaults) ──────────────────────────────
RESPONDER_MODEL = os.getenv("RESPONDER_MODEL", "gpt-4o-mini")
PERPLEXITY_MODEL = os.getenv("PERPLEXITY_MODEL", "sonar")
# How recent Perplexity results must be: "day" | "week" | "month" | "year".
# "week" = freshest; widen to "month"/"year" if a run comes back too thin.
PERPLEXITY_RECENCY = os.getenv("PERPLEXITY_RECENCY", "week")
