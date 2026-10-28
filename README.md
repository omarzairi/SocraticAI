# SocraticAI

A Socratic tutor with long-term memory. You pick a topic and the tutor answers with guiding questions instead of answers: it surfaces misconceptions with counter-examples and gives smaller hints when you're stuck. When you end a session, it writes notes about you (progress, knowledge gaps, misconceptions, learning preferences). Those notes personalize your next sessions, and you can read, correct or delete them at any time.

Built for the Raiselabs internship take-home. How AI tools were used, including the bugs and design flaws they caught, is in [AI_WORKFLOW.md](AI_WORKFLOW.md). The approved plan is in [docs/plan.md](docs/plan.md).

## Run it locally

You need [uv](https://docs.astral.sh/uv/), which installs Python 3.13 for you, Node.js 20.9 or newer, and a free API key from [console.groq.com](https://console.groq.com/keys).

**Backend** (http://127.0.0.1:8000, API docs at `/docs`):

```bash
cd backend
cp .env.example .env        # then set LLM_API_KEY in .env
uv sync
uv run fastapi dev
```

**Frontend** (http://localhost:3000), in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

**Tests and checks:**

```bash
cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .
cd frontend && npm run lint && npm run build   # build includes the TypeScript check
```

The tests never call the real LLM. They use a scripted fake, and test settings point at an unreachable URL with a dummy key.

To reset all data, stop the backend and delete `backend/data/app.db`. There are no migrations; see "With more time".

## Architecture

```
Next.js (client components) ──fetch/CORS──▶ FastAPI routers   HTTP only: validation, status codes
                                               │
                                               ▼
                                            services          rules, transactions, LLM calls
                                         ┌─────┴─────┐
                                         ▼           ▼
                                  repositories    LLMClient ──▶ Groq (openai/gpt-oss-120b)
                                   (SQL only)      (Protocol; tests use FakeLLMClient)
                                         ▼
                                      SQLite
```

- **Backend** (`backend/app`):
  - `routers/`, `services/` and `repositories/` are plain functions that take a connection (and the LLM client when needed).
  - Prompts live in `app/prompts/*.md`.
  - Settings are in `config.py` and read from `.env`.
- **Frontend** (`frontend/src`):
  - Every page is a client component that calls the API through `lib/api.ts`.
  - The pages are: learner picker → sessions → chat → memory.

## Design decisions

**Tutoring.** `tutor_system.md`:
- asks for exactly one guiding question per reply;
- diagnoses what the learner already knows first;
- exposes misconceptions with a question or counter-example rather than a correction;
- uses a hint ladder;
- never gives the answer because the learner asked twice. Demands get a smaller hint instead.

Long chats are trimmed to a character budget, because the free tier limits tokens per minute. The kept part always starts with a tutor turn, so user and assistant roles keep alternating. You can check prompt changes by hand with `uv run python -m scripts.try_tutor`.

**Memory**, one typed note per row (`progress`, `knowledge_gap`, `misconception`, `preference`):
- **Why rows.** Rows can be inspected, corrected and deleted one by one, and the rules can be tested in code. A single summary paragraph drifts, can't be partly corrected, and would overwrite the learner's edits.
- **Extraction.** Ending a session sends the transcript (as JSON, so a learner can't fake a tutor turn) and the current notes to the LLM in JSON mode. It proposes `create`, `update` or `archive` operations.
- **The code decides.**
  - Each operation is validated on its own.
  - The SQL itself refuses changes to notes that are archived, belong to another learner, or were edited by the learner (`… AND user_edited = 0`, with the rowcount checked).
  - Duplicates and repeated operations are skipped.
- **All-or-nothing ending.** The session becomes `ended` in the same transaction that applies the notes. If the LLM fails or replies with garbage, nothing changes and you just end the session again. So "ended" always means "memory updated".
- **Retrieval.** Every tutor turn re-reads your active notes (at most 8 per kind), so an edit applies from your next message. They are framed as information, never instructions.
- **Your control.** Editing a note locks it against the extractor for good. Deleting really deletes it.

**Consistency.** Every LLM call follows one pattern: read, call the LLM (no lock held), then `BEGIN IMMEDIATE`, re-check that nothing changed, write, commit. Races such as a second tab or ending mid-reply give a clear 409 instead of a corrupted conversation. Deterministic tests use a fake LLM that runs code mid-call.

**Choices:**
- **Groq `gpt-oss-120b`:** a stable model on Groq's free tier, fast, with JSON mode. Groq retired its Llama models for free accounts in 2026.
- **SQLite:** zero setup, and every query is visible.
- **One active session per learner:** memory evolves in a clean order.
- **Calls go straight to FastAPI over CORS:** Next.js rewrites have a 30 s proxy timeout, which a slow LLM call can exceed.

## Demo: one session, then a return visit

A recorded video of the UI going through both sessions with the real model is [docs/demo/socratic-demo.webm](docs/demo/socratic-demo.webm). To re-record it (both servers running), run `cd frontend && node scripts/record-demo.mjs`. A real transcript from the model, covering both sessions and the memory updates, is in [docs/demo/DEMO.md](docs/demo/DEMO.md). To regenerate it (it uses a throw-away database), run `cd backend && uv run python -m scripts.demo_two_sessions > ../docs/demo/DEMO.md`. To try it in the UI:

1. Create the learner "Alex" and start a session on *Adding fractions*. When asked, claim that 1/2 + 1/3 = 2/5. The tutor answers with a question, not a correction.
2. End the session. "What I learned about you" lists the misconception, plus a knowledge gap or preference.
3. Open "What the tutor remembers" and edit one note. It is marked "edited by you".
4. Start a new session on the same topic. The opening refers to last time, and the tutor checks whether the misconception is still there.
5. Get it right (1/2 + 1/3 = 5/6) and end the session. The misconception moves to "No longer applies" and a progress note appears. The note you edited is untouched.

## With more time

- Migrations (Alembic) and a server database (PostgreSQL) for multi-user hosting.
- Auth, streaming replies, and Docker. These were out of scope by design.
- Semantic retrieval (embeddings) once a learner has many notes.
- A change history per note.
- Suggested updates for notes you have locked, which you approve.
- Summarizing long sessions instead of trimming them.
- Frontend tests (Playwright end-to-end), types generated from the OpenAPI schema, and an automated evaluation of tutoring quality.
