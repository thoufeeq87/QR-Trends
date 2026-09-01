import os
import secrets

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
INGEST_SECRET = os.environ.get("INGEST_SECRET", "")
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", "")
PORT = int(os.environ.get("PORT", "8000"))

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

# Falls back to a random key so the app still boots without one set (e.g. first local
# run before .env is filled in) — but that means sessions won't survive a restart.
# MUST be set explicitly in Railway (same as INGEST_SECRET) or every deploy logs
# everyone out.
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY") or secrets.token_hex(32)

ALLOWED_EMAILS = {
    email.strip().lower() for email in os.environ.get("ALLOWED_EMAILS", "").split(",") if email.strip()
}
