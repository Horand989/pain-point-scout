"""
Offline test of scoring + responder against fixed sample data.
Run from the project root:   python tests/test_pipeline.py
Verifies classification, ranking, and drafting without any live API calls.
"""
import os
import sys
import logging

# make project root importable when run as a script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.sample_results import SAMPLE
from scoring import classify_and_score
from responder import draft_responses

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("test")


def run():
    results = [r for r in SAMPLE]  # copy refs
    top_a, all_a, type_b = classify_and_score(results, log)

    # Reddit + Quora items must be Type A.
    for r in SAMPLE:
        if r.source in ("reddit", "quora"):
            assert r.result_type == "A", f"{r.source} item should be Type A"

    # The pure listicle blog (google, non-discussion) should be Type B.
    blog = next(r for r in SAMPLE if r.url == "https://someblog.com/best-ai-tools")
    assert blog.result_type == "B", "listicle blog should be a Type B build signal"

    # A Google-surfaced Reddit question should be Type A (engageable).
    surfaced = next(r for r in SAMPLE if "Affiliatemarketing" in r.url)
    assert surfaced.result_type == "A", "google-surfaced reddit question should be Type A"

    # Ranking: sorted descending, ranks assigned 1..n.
    assert all(top_a[i].score >= top_a[i + 1].score for i in range(len(top_a) - 1)), "not sorted"
    assert [r.rank for r in top_a] == list(range(1, len(top_a) + 1)), "ranks not 1..n"

    # Responder (dry run) attaches a draft to every top item.
    draft_responses(top_a, log, dry_run=True)
    assert all(r.draft_response for r in top_a), "every top item needs a draft"

    print("\n--- RESULT ---")
    print(f"Type A: {len(all_a)}   Type B: {len(type_b)}   Top: {len(top_a)}")
    for r in top_a:
        print(f"  #{r.rank}  {r.score:>5}  [{r.source}]  {r.title[:60]}")
    print("\nALL ASSERTIONS PASSED")


if __name__ == "__main__":
    run()
