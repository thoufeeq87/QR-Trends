from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import INGEST_SECRET
from app.db import SessionLocal, ensure_schema
from app.pipeline import run_ingest
from app.queries import SECTION_TREND_LABELS, get_topic_card, get_topic_cards
from app.schemas import IngestSummary, TopicCard

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="QA Pulse")


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
    if not INGEST_SECRET or x_ingest_secret != INGEST_SECRET:
        raise HTTPException(status_code=401, detail="invalid or missing X-Ingest-Secret")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/topics", response_model=list[TopicCard])
def list_topics(section: str, db: Session = Depends(get_db)) -> list[dict]:
    if section not in SECTION_TREND_LABELS:
        raise HTTPException(status_code=400, detail=f"section must be one of {list(SECTION_TREND_LABELS)}")
    return get_topic_cards(db, section)


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
