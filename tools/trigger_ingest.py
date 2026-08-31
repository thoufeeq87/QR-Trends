"""Entry point for the Railway "ingest-cron" service. See workflows/deploy_railway.md.

This service exists only to POST to the web service's protected /api/ingest on a
schedule (Railway's Cron Jobs re-run a service's start command — it doesn't offer
"hit this URL on a schedule" directly, so a tiny caller service is the correct shape).
Reads WEB_URL and INGEST_SECRET from env; run as `python tools/trigger_ingest.py`.
"""

import os
import sys

import requests

def _with_scheme(url: str) -> str:
    url = url.rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url


WEB_URL = _with_scheme(os.environ["WEB_URL"])
INGEST_SECRET = os.environ["INGEST_SECRET"]
TIMEOUT = 120  # a full ingest run (fetch + Claude tagging) can take a while


def main() -> int:
    resp = requests.post(
        f"{WEB_URL}/api/ingest",
        headers={"X-Ingest-Secret": INGEST_SECRET},
        timeout=TIMEOUT,
    )
    print(f"POST /api/ingest -> {resp.status_code}: {resp.text}")
    resp.raise_for_status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
