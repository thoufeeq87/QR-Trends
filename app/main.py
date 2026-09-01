import hmac
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.auth import AuthMiddleware, router as auth_router
from app.config import INGEST_SECRET, SESSION_SECRET_KEY
from app.db import SessionLocal, ensure_schema
from app.pipeline import run_ingest
from app.queries import SECTION_TREND_LABELS, get_last_ingested_at, get_topic_card, get_topic_cards
from app.schemas import IngestSummary, StatusResponse, TopicCard, TopicSection

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="QA Pulse")

# Middleware order matters: Starlette wraps in reverse of add_middleware() call
# order, so the LAST one added ends up outermost (runs first on each request).
# AuthMiddleware reads request.session, so SessionMiddleware must run before it —
# added second here, verified empirically in local testing.
app.add_middleware(AuthMiddleware)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY, same_site="lax")
app.include_router(auth_router)


@app.on_event("startup")
def on_startup() -> None:
    ensure_schema()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_ingest_secret(x_ingest_secret: str = Header(default="")) -> None:
    if not INGEST_SECRET or not hmac.compare_digest(x_ingest_secret, INGEST_SECRET):
        raise HTTPException(status_code=401, detail="invalid or missing X-Ingest-Secret")


@app.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "ok"}


@app.get("/api/status", response_model=StatusResponse)
def status(db: Session = Depends(get_db)) -> dict:
    return {"last_ingested_at": get_last_ingested_at(db)}


@app.get("/api/topics", response_model=TopicSection)
def list_topics(section: str, limit: int = 30, offset: int = 0, db: Session = Depends(get_db)) -> dict:
    if section not in SECTION_TREND_LABELS:
        raise HTTPException(status_code=400, detail=f"section must be one of {list(SECTION_TREND_LABELS)}")
    if not (1 <= limit <= 100):
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")
    return get_topic_cards(db, section, limit=limit, offset=offset)


@app.get("/api/topics/{topic_id}", response_model=TopicCard)
def get_topic(topic_id: int, db: Session = Depends(get_db)) -> dict:
    card = get_topic_card(db, topic_id)
    if card is None:
        raise HTTPException(status_code=404, detail="topic not found")
    return card


@app.post("/api/ingest", response_model=IngestSummary, dependencies=[Depends(require_ingest_secret)])
def ingest(db: Session = Depends(get_db)) -> dict:
    return run_ingest(db)


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
