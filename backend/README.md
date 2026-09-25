# PRism — backend

FastAPI + PostgreSQL + SQLAlchemy async + Alembic.

## Quick start

```bash
# 1. Create virtualenv
python3 -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure database URL (copy and edit)
cp .env.example .env

# 4. Run migrations (PostgreSQL must be running)
alembic upgrade head

# 5. Start dev server
uvicorn app.main:app --reload
```

## Project layout

```
backend/
├── app/
│   ├── main.py            # FastAPI app entry point
│   ├── config.py          # Pydantic settings
│   ├── database.py        # Async engine + session factory
│   ├── models.py          # SQLAlchemy ORM models (PR, Analysis, Facet, Finding)
│   ├── schemas.py         # Pydantic request/response schemas
│   ├── routers/
│   │   └── analyses.py    # POST /analyses, GET /analyses/{id}, GET /analyses/{id}/stream
│   └── ingestion/
│       ├── bundle.py      # PRBundle dataclass (normalised PR struct)
│       ├── diff_parser.py # Unified diff → FilePatch list
│       ├── file_ingestion.py   # Raw diff + metadata → PRBundle
│       └── github_ingestion.py # GitHub PR URL → PRBundle (stub; real API calls in Step 3)
├── alembic/
│   └── versions/
│       └── 0001_initial_schema.py  # First migration
├── alembic.ini
└── requirements.txt
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/analyses` | Create analysis from `{ github_pr_url }` or `{ diff, title, description }` |
| `GET`  | `/analyses/{id}` | Analysis status + completed facets |
| `GET`  | `/analyses/{id}/stream` | SSE stream; emits `ping` then `done` events |
| `GET`  | `/healthz` | Health check |
