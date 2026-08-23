# Financial Filings Analyzer

A backend service for uploading financial filings (PDF) and asking natural-language
questions about them, answered by an LLM. Built with FastAPI, PostgreSQL, and the
Claude API.

This project is intentionally backend-focused: the LLM is one component in a system
that emphasizes clean API design, authentication, data modeling, testing, and the
engineering required to use an LLM reliably (chunking long documents, retrying
transient failures, and caching to avoid redundant calls).

## Features

- **JWT authentication** — register/login with bcrypt-hashed passwords; every
  document and analysis is scoped to its owner.
- **PDF upload & text extraction** — filings are parsed once on upload and the
  extracted text is stored, so analysis never re-parses the file.
- **LLM-powered Q&A** — ask questions about a filing and get answers grounded in
  its text.
- **Handles long documents** — filings that exceed a single model context are split
  into overlapping chunks and answered via a map-reduce over those chunks.
- **Resilient LLM calls** — transient API errors are retried with exponential
  backoff; client-side (4xx) errors fail fast instead of retrying pointlessly.
- **Answer caching** — an identical question on the same document returns the stored
  answer instead of making another (paid) LLM call.
- **Production shape** — Alembic migrations, Docker Compose, global exception
  handling, health check, structured logging.

## Architecture

```
Client
  │  HTTP + JWT
  ▼
FastAPI app  (app/main.py)
  ├── /auth        register / login            (app/api/auth.py)
  ├── /documents   upload / list / get         (app/api/documents.py)
  └── /documents/{id}/analyses  ask / list     (app/api/analyses.py)
        │
        ├── PDF text extraction   (app/services/pdf_service.py)
        ├── Chunking              (app/services/chunking.py)
        └── LLM analysis          (app/services/llm_service.py) ──► Claude API
        │
        ▼
   PostgreSQL  (users, documents, analyses)
```

### Key design decisions

**Extracted text is stored on upload.** Parsing a PDF is comparatively expensive,
and a filing is analyzed many times but uploaded once. Storing `extracted_text` on
the `Document` row means every subsequent question skips re-parsing.

**Long documents use map-reduce.** A single filing can be far larger than is
sensible to send in one prompt. The text is split into overlapping chunks; the
question is asked against each chunk ("map"), and the partial answers are
synthesized into one final answer ("reduce"). The overlap prevents losing context
for content that straddles a chunk boundary.

**Retries distinguish transient from permanent failures.** Server errors and rate
limits (5xx / 429) are retried with exponential backoff. Client errors (other 4xx)
indicate a bad request and are surfaced immediately rather than retried.

**Caching lives at the analysis layer.** Before calling the LLM, the service checks
whether the exact question has already been answered for that document. This is a
correctness-preserving optimization that directly reduces API cost.

**Ownership checks return 404, not 403.** Requesting another user's document returns
"not found" rather than "forbidden", so the API doesn't leak the existence of
documents belonging to other users.

## Tech stack

- **FastAPI** — web framework
- **SQLAlchemy 2.x** + **PostgreSQL** — ORM and database
- **Alembic** — database migrations
- **python-jose** + **bcrypt** — JWT auth and password hashing
- **pypdf** — PDF text extraction
- **anthropic** — Claude API client
- **pytest** — unit and integration tests

## Getting started

### With Docker (recommended)

```bash
cp ..env.example ..env          # then set ANTHROPIC_API_KEY and a real SECRET_KEY
docker compose up --build
```

The API will be available at `http://localhost:8000`. Migrations run automatically
on startup. Interactive API docs are at `http://localhost:8000/docs`.

### Locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ..env.example ..env          # set DATABASE_URL, SECRET_KEY, ANTHROPIC_API_KEY
alembic upgrade head
uvicorn app.main:app --reload
```

## Running the tests

```bash
pytest
```

The suite has two layers:

- **Unit tests** (`tests/test_unit.py`) — security helpers, chunking, PDF
  extraction, and the LLM service logic (single-call, map-reduce, and retry paths),
  with the Claude client mocked.
- **Integration tests** (`tests/test_integration.py`) — full HTTP flows through the
  real app: auth, upload validation, ownership isolation, and analysis with caching.
  These use an in-memory SQLite database via a dependency override, so no external
  database is required and the suite is fast and deterministic.

The LLM is mocked throughout the tests, so they run without an API key and cost
nothing.

## API reference

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Create an account |
| POST | `/auth/login` | Get a JWT access token |
| POST | `/documents` | Upload a PDF filing |
| GET | `/documents` | List your documents |
| GET | `/documents/{id}` | Get one document |
| POST | `/documents/{id}/analyses` | Ask a question about a document |
| GET | `/documents/{id}/analyses` | List past questions & answers |
| GET | `/health` | Health check |

All `/documents` routes require an `Authorization: Bearer <token>` header.

## Future work

- Token-accurate chunking (currently uses a character-based approximation).
- OCR for scanned/image-only PDFs (currently text-based PDFs only).
- Live SEC EDGAR ingestion (currently upload-based).
- Streaming responses for long analyses.
- Rate limiting per user.
