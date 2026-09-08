"""
Reddit source — official API via PRAW (read-only).

Most reliable, lowest-risk source. PRAW handles auth + rate limiting.
Returns a standardized list[Result]. Never crashes the run: on any error
it logs and returns what it has so far.
"""
import os
from datetime import datetime, timezone

from .base import Result


def fetch(queries, limits, logger):
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "pain-point-scout/0.1")

    if not client_id or not client_secret:
        logger.warning("Reddit: REDDIT_CLIENT_ID/SECRET not set — skipping this source.")
        return []

    try:
        import praw
    except ImportError:
        logger.error("Reddit: praw not installed (pip install praw) — skipping.")
        return []

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            check_for_async=False,
        )
        reddit.read_only = True
    except Exception as e:
        logger.error(f"Reddit: could not initialize client: {e}")
        return []

    posts_per_query = limits.get("posts_per_query", 12)
    comments_per_post = limits.get("comments_per_post", 4)
    subreddits = limits.get("subreddits") or ["all"]
    max_queries = limits.get("max_queries", 8)

    out = []
    seen_ids = set()

    for q in queries[:max_queries]:
        for sub in subreddits:
            try:
                listing = reddit.subreddit(sub).search(
                    q, sort="relevance", time_filter="year", limit=posts_per_query
                )
                for post in listing:
                    if post.id in seen_ids:
                        continue
                    seen_ids.add(post.id)

                    body = (getattr(post, "selftext", "") or "")[:800]

                    # Pull a few top comments — richest pain language lives there.
                    comment_text = ""
                    try:
                        post.comments.replace_more(limit=0)
                        tops = [c.body for c in post.comments[:comments_per_post] if getattr(c, "body", "")]
                        if tops:
                            comment_text = "\n\nTOP COMMENTS:\n" + "\n".join(f"- {t[:300]}" for t in tops)
                    except Exception as ce:
                        logger.info(f"Reddit: could not load comments for {post.id}: {ce}")

                    created = ""
                    try:
                        created = datetime.fromtimestamp(post.created_utc, tz=timezone.utc).isoformat()
                    except Exception:
                        pass

                    out.append(Result(
                        source="reddit",
                        title=post.title or "",
                        url=f"https://www.reddit.com{post.permalink}",
                        summary=(body[:280] or post.title or ""),
                        raw_snippet=f"[r/{getattr(post.subreddit, 'display_name', sub)}] {post.title}\n{body}{comment_text}",
                        timestamp=created,
                    ))
            except Exception as e:
                logger.error(f"Reddit: search failed for '{q}' in r/{sub}: {e}")
                continue

    logger.info(f"Reddit: collected {len(out)} items.")
    return out
