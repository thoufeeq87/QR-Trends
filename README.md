# QA Pulse

Tracks what topics are trending, stable, or fading in the software QA/testing niche —
ingests from ~13 QA/testing sources daily, uses Claude to tag topics, classifies
momentum, and shows it on a dashboard. Built on the WAT architecture — see
[`docs/PRD.md`](docs/PRD.md) for the full plan and [`workflows/deploy_railway.md`](workflows/deploy_railway.md)
to deploy it.

## Local development

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL, ANTHROPIC_API_KEY, INGEST_SECRET
python -m tools.seed_sources
uvicorn app.main:app --reload
```
