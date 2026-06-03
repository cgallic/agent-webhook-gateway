"""
Sample async job — "summarize a topic".

A self-contained mock job that simulates a slow background task. It sleeps for
a few seconds (to mimic real work), then returns a deterministic, fake
structured summary built from the requested topic.

There is NO external network access, NO secrets, and NO real data here. All
numbers and bullet points are clearly-labeled demo fixtures. This exists only
to demonstrate the gateway's async job queue (create -> submit -> poll /jobs)
without requiring any private routers or configuration.
"""

import time
from datetime import datetime
from typing import Any, Dict

# How long the mock job "works" for, in seconds. Kept short so the demo feels
# responsive while still exercising the pending -> running -> completed flow.
DEFAULT_DURATION_SECONDS = 3

# Fictional sample product used throughout the demo. Not a real company.
SAMPLE_PRODUCT = "PingDesk"


def summarize_topic(topic: str, duration_seconds: int = DEFAULT_DURATION_SECONDS) -> Dict[str, Any]:
    """
    Pretend to research and summarize a topic.

    Args:
        topic: The topic to "summarize" (free text from the demo form).
        duration_seconds: How long to sleep, simulating slow background work.

    Returns:
        A dict with a fake structured summary. Stored verbatim as the job result.
    """
    topic = (topic or "").strip() or "an unspecified topic"

    # Clamp the sleep so a malicious/large value can't hang a worker.
    duration_seconds = max(0, min(int(duration_seconds), 10))

    started = datetime.utcnow().isoformat()

    # Simulate slow work (e.g. an LLM call or a crawl) without any real I/O.
    time.sleep(duration_seconds)

    finished = datetime.utcnow().isoformat()

    # Build a deterministic, obviously-fake summary from the topic text. The
    # word count drives a couple of fake "metrics" so the dashboard has numbers
    # to render — all labeled as demo data.
    word_count = len(topic.split())
    fake_confidence = min(99, 60 + word_count * 3)

    return {
        "topic": topic,
        "summary": (
            f"Demo summary for '{topic}'. This is sample output from the "
            f"{SAMPLE_PRODUCT} demo job — a hypothetical small-business SaaS — "
            "and contains no real analysis."
        ),
        "key_points": [
            f"'{topic}' matters most to small teams without dedicated staff (sample insight).",
            f"A hypothetical {SAMPLE_PRODUCT} workflow could automate the repetitive parts (sample insight).",
            "Demo data only — replace this job with your own background task.",
        ],
        "sample_metrics": {
            "estimated_reading_time_seconds": word_count * 2,
            "confidence_score": fake_confidence,
            "note": "All metrics are fabricated demo values, not measurements.",
        },
        "timing": {
            "started_at": started,
            "finished_at": finished,
            "simulated_work_seconds": duration_seconds,
        },
    }


if __name__ == "__main__":
    # Allow running the job directly for a quick smoke test:
    #   python -m demo.sample_job "your topic here"
    import json
    import sys

    requested_topic = " ".join(sys.argv[1:]) or "how to answer the phone after hours"
    print(json.dumps(summarize_topic(requested_topic), indent=2))
