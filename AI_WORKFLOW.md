# AI Workflow

This file covers how I used AI coding tools to build this project. It also records where the AI got things wrong and how each problem was caught and fixed. The log is written as the work happens, not afterwards.

## Tools

- **Claude Code (Opus 5.5)** as the main coding agent, with these plugins:
  - `superpowers`, for discipline: brainstorm and plan before building.
  - `feature-dev`, to build one feature at a time: explore, design, implement, review.
  - `pr-review-toolkit`, whose `silent-failure-hunter`, `pr-test-analyzer` and `code-reviewer` agents run on every feature's diff.
  - `frontend-design`, for the UI.
- **Research subagents** to check the current official docs (Next.js, FastAPI, openai SDK, Groq) instead of trusting the model's memory. The model's knowledge stops before several recent breaking changes (see entries 1–5).

## Process

1. **Plan before code.** The agent read the brief and proposed a plan in plan mode, with no code written: repo structure, data model, API, LLM provider, and memory design with tradeoffs. I approved it before anything was built. The plan is in [`docs/plan.md`](docs/plan.md).
2. **Independent reviews of the plan.** Two reviewer agents critiqued the draft from opposite angles: correctness and failure modes, versus simplicity and explainability. Their findings and how they were resolved are in entries 6–8.
3. **Written rules.** [`CLAUDE.md`](CLAUDE.md) encodes the architecture rules, memory invariants and workflow, so every later step follows the same rules.
4. **One loop per feature:** feature branch → implement with tests → commit → review agents on the diff → fix real issues → log them here → merge into `main`.

## Log: problems found and how they were fixed

Each entry records what was generated, the problem, how it was caught, and the fix.

### Planning phase

1. **Retired LLM model.**
   - **Generated:** the agent's first candidate, recalled from memory, was Groq's `llama-3.3-70b-versatile`.
   - **Problem:** Groq shut that model down for free and developer accounts on 2026-08-16, so the app would have failed on its first request. Most other well-known Groq models (`llama-4-*`, `qwen3-32b`, `kimi-k2`) were retired in 2026 too.
   - **Caught by:** a research subagent checking Groq's live models and deprecations pages.
   - **Fix:** use `openai/gpt-oss-120b`, a production model on the free tier, with `openai/gpt-oss-20b` as the fallback. The model id lives only in `.env`.
2. **Next.js 16.4 turns on Cache Components by default.**
   - **Problem:** with it on, calling `useParams()` on a dynamic route needs a `<Suspense>` boundary or `next build` fails. The failure only appears at build time, not in `next dev`, so it would have surfaced late.
   - **Caught by:** docs research.
   - **Fix:** scaffold with `--no-cache-components`. This app renders entirely on the client.
3. **Rewrite proxy timeout.**
   - **Problem:** proxying `/api` through Next.js `rewrites` is a common way to avoid CORS, but the proxy has an undocumented 30 s default timeout. An LLM call plus SDK retries can take longer, so the UI would show an error while the backend still saved the message.
   - **Caught by:** docs and source research.
   - **Fix:** the browser calls FastAPI directly, with CORS configured on the backend.
4. **openai SDK 3.x moved to `httpx2`.**
   - **Generated:** from memory, the agent planned to mock the SDK in tests with `httpx.MockTransport`.
   - **Problem:** openai-python 3.0 (August 2026) switched its HTTP client to `httpx2`, so that mock would no longer apply.
   - **Fix:** the tests inject `httpx2.MockTransport`.
5. **Commit placement in FastAPI dependencies.**
   - **Problem:** committing the database transaction after `yield` in a dependency looks clean, but current FastAPI runs that code *after* the response has been sent. A failed commit would never reach the client.
   - **Caught by:** reading the "dependencies with yield" docs.
   - **Fix:** services commit explicitly inside a `transaction()` helper. The dependency only closes the connection.
6. **Correctness review of the draft plan (accepted).** A reviewer agent found real issues:
   - **(a) Retry state machine.** The draft's "memory extraction failed → retry" design had an unguarded status change that could apply memory operations twice, and a crash could leave a session stuck as "ended but never extracted".
   - **(b) Chat history trimming.** Cutting history by message count could put two learner messages next to each other, which some chat templates reject.
   - **(c) Timestamps on Windows.** Python's clock is coarse enough on Windows that rows inserted back to back share a timestamp, so `ORDER BY created_at` is nondeterministic.
   - **(d) Oversized ids.** A path id like `99999999999999999999` passes `int` validation, then crashes sqlite3 with a 500.
   - **(e) Restored memories.** Restoring an archived memory didn't lock it, so the extractor could archive it again.
   - **(f) Race.** "Send message" and "end session" could interleave.
   - **Fixes:**
     - For (a), see entry 7.
     - History is trimmed by a character budget and always starts with a tutor message.
     - Rows are ordered by `id`.
     - Path ids use a bounded type.
     - Any learner change locks the memory.
     - `BEGIN IMMEDIATE` transactions re-check state after every LLM call, with deterministic race tests that use a scripted fake LLM.
7. **Simplicity review, and resolving a disagreement between the two reviewers.**
   - **The disagreement:** a second reviewer argued that the retry machinery was the hardest code in the plan to explain. It proposed making "end session" all-or-nothing: extraction and ending happen in one transaction, and on failure nothing changes and the learner clicks End again. The first reviewer had instead proposed hardening the retry state machine.
   - **The choice:** the agent recommended all-or-nothing, and I approved it as part of the plan. It removes the bugs in 6(a) instead of patching them, and the invariant "ended ⇒ memory updated" is easy to test.
   - **Also cut, because the brief doesn't require them:**
     - learner-added memories, editing a memory's kind, archive/restore
     - configurable CORS origins (a list in an env var must be JSON, which is easy to get wrong)
     - frontend unit tests and a GIF demo
8. **Rejected suggestion.**
   - **Proposed:** a `memory_changes` audit table, so revisiting an old session could show what memory it changed.
   - **Decision:** deferred to "with more time". It's useful but not required, and the end-of-session summary card already shows memory changes for the demo.
