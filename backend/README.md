# PRism — backend

FastAPI + PostgreSQL + SQLAlchemy async + Alembic.

## Quick start

```bash
# 1. Create virtualenv
python3 -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure database URL and storage (copy and edit)
cp .env.example .env

# 4. Run migrations (PostgreSQL must be running)
alembic upgrade head

# 5. Start dev server
uvicorn app.main:app --reload
```

## Review provider

Gemini is the default review provider. Add the key to `backend/.env` and set
the model there; the default model supports structured outputs:

```env
REVIEW_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-3.1-flash-lite
```

The optional OpenAI adapter can be selected with `REVIEW_PROVIDER=openai`,
`OPENAI_API_KEY`, and `OPENAI_MODEL`. Provider calls only propose findings;
the deterministic evidence gate still verifies every citation before storage.

## Project layout

```
backend/
├── app/
│   ├── main.py            # FastAPI app entry point
│   ├── config.py          # Pydantic settings (DB, storage)
│   ├── database.py        # Async engine + session factory
│   ├── models.py          # SQLAlchemy ORM models (PR, Analysis, Facet, Finding)
│   ├── schemas.py         # Pydantic request/response schemas
│   ├── routers/
│   │   └── analyses.py    # POST /analyses, GET /analyses/{id},
│   │                      # GET /analyses/{id}/diff, GET /analyses/{id}/stream
│   ├── ingestion/
│   │   ├── bundle.py      # PRBundle dataclass (normalised PR struct)
│   │   ├── diff_parser.py # Unified diff → FilePatch list
│   │   ├── file_ingestion.py   # Raw diff + metadata → PRBundle
│   │   └── github_ingestion.py # GitHub PR URL → PRBundle (stub)
│   └── storage/
│       ├── base.py        # ArtifactStore ABC + StoredArtifact dataclass
│       ├── local.py       # LocalArtifactStore (dev default)
│       ├── s3.py          # S3ArtifactStore (production)
│       ├── factory.py     # Singleton factory; selects backend from settings
│       └── keys.py        # Stable object key generators
├── alembic/
│   └── versions/
│       ├── 0001_initial_schema.py              # prs, analyses, facets, findings
│       └── 0002_add_artifact_storage_columns.py # diff_storage_key, diff_size_bytes, diff_sha256
├── tests/
│   └── test_storage.py    # Storage layer tests (no real AWS calls)
├── alembic.ini
├── requirements.txt
└── .env.example
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/analyses` | Create analysis from `{ github_pr_url }` or `{ diff, title, description }` |
| `GET`  | `/analyses/{id}` | Analysis status + completed facets |
| `GET`  | `/analyses/{id}/diff` | Return the raw diff artifact (served through the backend — bucket stays private) |
| `GET`  | `/analyses/{id}/stream` | SSE stream; emits `ping` then `done` events |
| `GET`  | `/healthz` | Health check |

## Artifact storage

Diffs are stored outside the database via a pluggable `ArtifactStore`.
PostgreSQL holds only metadata: `diff_storage_key`, `diff_size_bytes`, `diff_sha256`.

### Local (development default)

```env
STORAGE_BACKEND=local
LOCAL_ARTIFACT_ROOT=/tmp/prism-artifacts
```

No extra setup needed.

### S3 (production)

```env
STORAGE_BACKEND=s3
S3_BUCKET_NAME=prism-artifact-storage-prismartifactbucket-ubri8x7giofh
AWS_REGION=ap-south-1
```

**Do not add AWS credentials to `.env` or source control.**
The SDK uses the default credential chain:

- Local dev: `~/.aws/credentials` or `AWS_PROFILE`
- EC2 / ECS: attach an IAM role to the instance/task (no long-lived keys)

### Required IAM permissions (bucket-scoped)

The runtime IAM principal needs at minimum:

```json
{
  "Effect": "Allow",
  "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
  "Resource": "arn:aws:s3:::prism-artifact-storage-prismartifactbucket-ubri8x7giofh/*"
}
```

> **Note:** The IAM role is not created by this task. It must be provisioned
> separately before deploying to a live environment. The bucket already exists
> (`prism-artifact-storage` CloudFormation stack, `ap-south-1`).

### Orphan artifact cleanup

When a `store.put` succeeds but the subsequent `db.commit()` raises, the
backend attempts to clean up the artifact.  Because a commit error has an
**ambiguous outcome** — PostgreSQL may have committed even if the application
did not receive confirmation — the backend always re-queries the database on a
fresh connection before deciding to delete.  The three possible outcomes are:

| DB check result | Action |
|---|---|
| Fresh DB confirms **no row** references the key | Artifact deleted via `store.delete` |
| Fresh DB finds a **row** referencing the key | Artifact preserved — commit succeeded despite the exception |
| Fresh DB query **fails** (database unreachable) | Artifact preserved; key logged at ERROR level for manual reconciliation |

**Versioned bucket behaviour:** The production bucket has versioning enabled.
`store.delete` calls `s3:DeleteObject`, which creates a **delete marker** on
the current object version rather than immediately removing the data.
Previous versions remain in the bucket until explicitly expired.  A lifecycle
rule based on key prefix alone cannot detect whether a given object version is
orphaned (has no matching database row), because S3 has no visibility into
database state.  Orphan identification requires a reconciliation job that
cross-references the bucket's object listing (including all versions) against
`prs.diff_storage_key` in the database.  This is not implemented yet; the log
messages at ERROR level serve as the signal for manual action until a
reconciliation job is added.

## Running tests

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

Tests use mocks — no PostgreSQL or AWS credentials required.
