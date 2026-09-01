import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
INGEST_SECRET = os.environ.get("INGEST_SECRET", "")
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", "")
PORT = int(os.environ.get("PORT", "8000"))
