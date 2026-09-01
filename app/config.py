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

# The public https:// URL this app is reachable at, e.g. https://qr-trends.up.railway.app
# (no trailing slash). Used to build the OAuth redirect_uri explicitly — deliberately
# NOT auto-detected from the incoming request, since that depends on Railway's proxy
# correctly forwarding scheme info to uvicorn, which turned out to be unreliable in
# practice (redirect_uri came out as http:// instead of https://, which Google
# rejects outright as a mismatch against the registered redirect URI).
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

# Falls back to a random key so the app still boots without one set (e.g. first local
# run before .env is filled in) — but that means sessions won't survive a restart.
# MUST be set explicitly in Railway (same as INGEST_SECRET) or every deploy logs
# everyone out.
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY") or secrets.token_hex(32)

ALLOWED_EMAILS = {
    email.strip().lower() for email in os.environ.get("ALLOWED_EMAILS", "").split(",") if email.strip()
}
