# CLAUDE.md

## Project

SocraticAI is a Socratic AI tutor with long-term learner memory, built as a take-home for Raiselabs. Learners chat with a tutor that asks guiding questions instead of giving answers. When a session ends, an LLM extracts memories about the learner (progress, knowledge gaps, misconceptions, preferences). Those memories personalize later sessions, and the learner can inspect, correct and delete them.

The approved plan is in `docs/plan.md`. The author must be able to explain every line, so prefer simple, explicit code over clever code.

## Stack (versions verified against official docs on 2026-10-27)

- **Backend:** Python 3.13 (managed by uv), FastAPI 0.162, Pydantic 2.14, pydantic-settings 2.16, stdlib `sqlite3`, and the `openai` SDK 3.x (built on `httpx2`) pointed at Groq's OpenAI-compatible API (`openai/gpt-oss-120b`).
- **Frontend:** Next.js 16.4 (App Router), React 19.3, TypeScript (strict), Tailwind v4, ESLint.
- **Tests:** pytest, FastAPI `TestClient`, `FakeLLMClient`.

## Commands

Backend (run from `backend/`):
- `uv sync`: install dependencies (uv downloads Python 3.13 if needed)
- `uv run fastapi dev`: dev server on http://127.0.0.1:8000 (OpenAPI docs at `/docs`)
- `uv run pytest`: run the tests
- `uv run ruff check .` and `uv run ruff format .`: lint and format

Frontend (run from `frontend/`):
- `npm install`, `npm run dev` (http://localhost:3000)
- `npm run lint`, `npm run build` (the build also type-checks)

CI (`.github/workflows/ci.yml`) runs the same backend and frontend checks on every push to `main` and every pull request.

## Backend architecture rules

**Layers and transactions**
- **Layers:** `routers/` → `services/` → `repositories/`, all written as plain functions that take `conn` (and `llm` where needed). No service or repository classes, no DI framework.
  - Routers do HTTP only: they receive validated input, call one service function and return a response model.
  - Services hold the business rules and transactions, and orchestrate LLM calls. They never import FastAPI.
  - Repositories run SQL only. They never commit and never call the LLM.
- **Transactions:** connections use `autocommit=True`. Services wrap every write in `with transaction(conn):`, which runs `BEGIN IMMEDIATE` … `COMMIT` / `ROLLBACK`. Never nest `transaction()`.
- **LLM consistency pattern:**
  1. Read what you need, outside any transaction.
  2. Call the LLM.
  3. `with transaction(conn):` re-check that what you read is still true, and raise `ConflictError` if it isn't.
  4. Write.
  - Never call the LLM inside a transaction. If the LLM fails, nothing is written.
- **Never commit in the `get_connection` yield-dependency.** FastAPI runs code after `yield` once the response has already been sent, so a failed commit there would be invisible.
- **`check_same_thread=False`** on every connection. FastAPI may run a sync dependency and the sync route on different threadpool threads; each connection still serves only one request.
- **Ordering:** order rows by `id` (`AUTOINCREMENT`). Timestamps are for display only (UTC ISO strings generated in Python). The one exception is memory recency, which orders by `updated_at DESC, id DESC`.

**Learner scoping**
- Every learner-owned resource lives under `/api/learners/{learner_id}/…`.
  - Queries on `sessions` and `memories` filter by `learner_id`.
  - `messages` are only read or written for a session already loaded with `session_service.get_session(conn, learner_id, session_id)`, which checks that the session belongs to that learner.
- Path ids use the `Id` alias (`1 … 2**63-1`), so oversized ids return 422 instead of crashing sqlite.

**Errors and validation**
- **Errors:** services raise `NotFoundError` (404), `ConflictError` (409) or `LLMError` (502), and `main.py` maps them in one place.
  - No broad `except Exception`.
  - Client errors (404 / 409 / 422) are returned to the caller, not logged; the server's access log already records them.
  - LLM failures and skipped extractor operations are logged with `logging` (never `print`).
  - Real bugs surface as 500s.
- **Validation:** Pydantic models guard every boundary.
  - Request bodies use `extra="forbid"`, stripped and length-limited strings, and `Literal` enums.
  - LLM output (memory operations) is validated the same way.

**Prompts, LLM and configuration**
- **Prompts** live only in `backend/app/prompts/*.md`. Render them with `string.Template.substitute`, never `safe_substitute`; write `$$` for a literal dollar sign. Keep prompt wording out of Python code.
- **LLM access** goes only through the `LLMClient` protocol in `app/llm.py`, injected with the `get_llm_client` dependency.
- **Memory kinds** are defined once (`MemoryKind` and its descriptions in `app/schemas.py`). Prompts and the frontend label map follow from that definition.
- **CORS** allows `http://localhost:3000` and `http://127.0.0.1:3000` with `allow_methods=["*"]`, because the default allows only GET.
- **Configuration** comes from pydantic-settings (`app/config.py` reads `backend/.env`). Never commit `.env`, and update `.env.example` whenever a setting changes.

## Memory invariants (each one is covered by tests)

1. The extractor never modifies or archives a memory with `user_edited = 1`. The SQL itself enforces this (`… WHERE … AND user_edited = 0`, then the rowcount is checked).
2. Ending a session is all-or-nothing: the session becomes `ended` in the same transaction that applies the memory operations. If the LLM fails or returns bad JSON, the API returns 502, nothing changes and the session stays active.
3. Each extractor operation is validated on its own and scoped to the learner. Invalid operations are skipped and logged.
4. Any change a learner makes to a memory sets `user_edited = 1`.

## Testing rules

- **Tests never call the real LLM.** Override `get_llm_client` with `FakeLLMClient`. Test settings use `_env_file=None`, a dummy key and `LLM_BASE_URL=http://llm.invalid`.
- **`FakeLLMClient` must fail loudly.** It raises `AssertionError` when a call wasn't scripted; never give it a silent default reply.
- **Every feature lands with tests that prove it.** Keep tests short by using the `conftest.py` helpers.

## Frontend rules

- Every page is a `"use client"` component, and ids come from `useParams()` (`next/navigation`). Don't use `useSearchParams`.
- The browser calls FastAPI directly through `lib/api.ts`, whose base URL defaults to `http://127.0.0.1:8000`. No Next API routes, server actions or rewrites.
- Never send a POST, PATCH or DELETE from `useEffect`. Disable buttons while a request is pending, and re-fetch after a change instead of patching local state.
- Use the frontend-design skill for UI work and keep it simple: no component library, no animation.

## Workflow rules

- **Check the docs.** Before using a Next.js or FastAPI API you're not sure about, read the current official docs (nextjs.org/docs, fastapi.tiangolo.com). Don't rely on memory.
- **One feature at a time.** Use the feature-dev workflow on a `feat/<name>` branch; `docs/plan.md` is the architecture.
- **Commits:**
  - Small, conventional commits (`feat(scope): …`, `fix`, `test`, `refactor`, `docs`, `chore`), with one concern per commit and tests green before each one.
  - No `Co-Authored-By` trailers and no AI-generated footers.
- **Review every feature.** Run the pr-review-toolkit agents (silent-failure-hunter, pr-test-analyzer, code-reviewer) on `git diff main...HEAD`. Fix real issues in separate `fix:` / `test:` commits; don't accept the first version that merely works.
- **Log problems right away.** Whenever a review, a test, a manual run or the user catches a bug or design flaw, append an entry to `AI_WORKFLOW.md` (what was generated, the problem, the fix, the commit). Also log suggestions you rejected and why.
- **Merging and pushing:** merge finished features into `main` with `--no-ff`. Never push without asking.
- **Out of scope:** Docker, auth and streaming.

## Style

- **Python:** type hints on all app code (tests may omit them), ruff for lint and format (line length 100), small functions, descriptive names.
- **TypeScript:** strict mode, ESLint.
- **Comments:** only for a non-obvious "why", never to restate the code.
