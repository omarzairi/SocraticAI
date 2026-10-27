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

### Step 1: backend skeleton and sessions

The step was built in 4 commits, each of which passes its own tests. Then `silent-failure-hunter`, `pr-test-analyzer` and `code-reviewer` reviewed the diff.

9. **A generated test checked a format instead of a property.**
   - **Generated:** `assert created_at.endswith("+00:00")`.
   - **Problem:** Pydantic writes UTC as `Z`. What matters is that the timestamp carries a timezone, because browsers read a timestamp without one as local time.
   - **Caught by:** running the tests.
   - **Fix:** parse the timestamp and assert `tzinfo is not None`.
10. **`transaction()` could hide the real database error** (silent-failure-hunter).
    - **Generated:** `except: ROLLBACK; raise`.
    - **Problem:** sometimes SQLite has already rolled back on its own (disk full, `INSERT OR ROLLBACK`). The helper's ROLLBACK then raised "cannot rollback - no transaction is active", which replaced the real error. A failed COMMIT also left the transaction open.
    - **Fix:**
      - COMMIT now runs inside the `try`, and ROLLBACK runs only `if conn.in_transaction`. This is the same approach as CPython's `Connection.__exit__`.
      - A regression test was confirmed to fail on the old code. (`137d5d6`)
11. **A typo in a setting silently fell back to the default database** (silent-failure-hunter).
    - **Generated:** `SettingsConfigDict(extra="ignore")`.
    - **Problem:** `DATABSE_PATH=…` in `.env`, or a misspelled keyword in a test, silently used `backend/data/app.db`. In tests that would mean the developer's real data. Also, `~` wasn't expanded, and a path pointing to a folder gave a cryptic error.
    - **Fix:** unknown keys are rejected (pydantic-settings' default, `forbid`), `~` is expanded, folders are rejected, and the resolved database path is logged at startup. (`5d62239`)
12. **Importing the app read the developer's `.env`** (pr-test-analyzer).
    - **Problem:** the module-level `app = create_app()` built `Settings()` while pytest was collecting tests.
    - **Fix:** settings are now created when the server starts, in the lifespan. A test makes sure building the app doesn't read them. (`ab33f13`)
13. **Tests that still passed on broken code** (pr-test-analyzer, mutation testing).
    - **How it was found:** the reviewer made 17 small deliberate bugs ("mutants") and 10 were not caught. Examples:
      - With `WHERE learner_id = ?` removed from the session list, one learner would see another's sessions.
      - Plain `BEGIN` instead of `BEGIN IMMEDIATE`.
      - With `check_same_thread=False` removed, 358 of 400 concurrent requests failed in the reviewer's probe.
      - An id limit of `2**64`.
      - A schema that drops tables on startup.
      - A missing CORS origin.
    - **Fix:** a test for each case. I re-ran the mutants to confirm every one is now caught. (`e13d3cb`, `54a336a`)
14. **Smaller fixes:**
    - The one-active-session rule is now also enforced by a partial unique index in the database. (`79211ce`)
    - A missing learner was reported as "Session … not found". (`1187da0`)
    - **CLAUDE.md overstated a rule** (code-reviewer). It said every query filters by `learner_id`, but messages are scoped through their session. I made the rule precise instead of adding a needless JOIN. (`a76b2f4`)
15. **Rejected or deferred:**
    - **Schema versioning with `PRAGMA user_version`:** there are no migrations by design, and the README documents resetting `app.db` after a schema change.
    - **A monkeypatch-based race test for two concurrent session starts:** deferred to step 2. There, the LLM call between the check and the insert allows a deterministic race test with the fake LLM, and the unique index already enforces the rule.
    - **Logging 404/409 responses:** these are client errors, not system failures, and the access log already records them.
16. **A guardrail was respected, not bypassed.**
    - **What happened:** my Claude Code settings deny reading `.env.*` files, to protect secrets. That rule also blocks writing `.env.example`.
    - **What the agent did:** it didn't work around the rule through the shell. It stopped and asked me how I wanted to handle it.

### Step 2: Socratic chat

17. **The server would have crashed without an API key** (caught by a generated test).
    - **Problem:** openai SDK 3.x raises an error when the client is created without a key. The plan says the server starts without one and tutor calls return a clear 502.
    - **Fix:** pass a placeholder key, which is never sent, because `complete()` refuses to call the provider until a real key is set. (`c7dfe02`)
18. **Cut-off replies were saved as complete** (silent-failure-hunter, reproduced).
    - **Example:** the stored opening read "Hi Alex! Before we start, tell me what you think a".
    - **Fix:** a reply with `finish_reason` of `length` or `content_filter` now raises "The tutor's reply was cut off". (`5cf55c0`)
19. **Odd provider responses became opaque 500s** (silent-failure-hunter, reproduced).
    - **Problem:** a non-JSON 200 (a captive portal, say), a broken JSON body, or a pasted key containing a smart quote all escaped as a 500. A 500 carries no CORS headers, so the UI could only say "server unreachable".
    - **Fix:** the client checks the response's shape and raises `LLMError` (a 502) instead. The key is validated at startup, and validation errors never echo input values. (`5cf55c0`, `a553729`)
20. **A single request could hang for about 5 minutes** (silent-failure-hunter).
    - **Problem:** a plain float timeout also raised the connect timeout to 30 s, and two SDK retries could each wait for `Retry-After` up to 120 s.
    - **Fix:** a 5 s connect timeout and a single retry. (`5cf55c0`, `a553729`)
21. **Two tabs could interleave one conversation** (code-reviewer and silent-failure-hunter).
    - **Problem:** the re-check after the LLM call only looked at the session's status. A reply could be saved although it had never seen the other tab's turn.
    - **Fix:** also re-check the message count, plus a race test. (`db21ee8`)
22. **A loophole in the Socratic prompt** (code-reviewer).
    - **Problems:**
      - "Give the answer if they ask more than once" let a learner skip all effort by asking twice.
      - Demands for the answer had no guidance.
      - "At most one question" allowed replies with no question.
      - Markdown and LaTeX would show up as raw symbols in a plain-text chat.
    - **Fix:** all four rules rewritten. (`a9d6837`)
    - **Still to do:** check against the real model with `scripts/try_tutor.py` once the API key is configured.
23. **Prompt edits were silently ignored in development** (code-reviewer).
    - **Problem:** `@cache` kept the first version of a prompt in memory, and `fastapi dev` only reloads on `.py` changes.
    - **Fix:** remove the cache. (`918cb4b`)
24. **Mutation testing, round 2** (pr-test-analyzer).
    - **Result:** 58 mutants, 16 meaningful survivors. For example: history not scoped to its session, the learner's message saved without the reply, a long chat sent untrimmed, and the real client wiring never exercised.
    - **Fix:** tests for each. Atomicity is proven with a SQLite trigger that makes the second insert fail. The fake LLM now also fails a test that leaves scripted replies unused. (`c4b1383`)
25. **My own mistakes in this step:**
    - A mutation-check command hung because of a stray `python3 -`, which on Windows is a Store alias waiting for input. The `git checkout` chained after it would have reverted uncommitted work. It never ran, and mutation checks now back up and restore the file instead.
    - A race test inserted `created_at='now'`, which the app (correctly) refused to parse.
26. **Rejected:**
    - **Stripping `OPENAI_ORG_ID` / `OPENAI_PROJECT_ID` headers:** this only matters if those environment variables are set, and org IDs aren't secrets.
    - **Parsing `Retry-After` to tell a daily quota from a per-minute limit:** a single message now mentions both.

### Step 3: memory pipeline

27. **Two reviewer agents were blocked, so I ran the mutation tests myself.**
    - **What happened:** the auto-mode classifier blocked the silent-failure and test-coverage reviewers. I didn't work around the block: the silent-failure reviewer was relaunched read-only, and I ran 11 mutants myself.
    - **Result:** one mutant survived. Removing `status = 'active'` from the update guard let the extractor rewrite archived memories, and no test noticed. Fixed with a new test. (`60b8350`)
    - **My own bug:** my mutation script wrote CRLF line endings on Windows. `git status` caught it, and the script now writes bytes exactly.
28. **A failed extraction looked like "nothing to remember"** (silent-failure-hunter).
    - **Problem:** if every operation was invalid, the session still ended, now with an empty update, and it could never be retried.
    - **Also fixed:** an unbounded `memory_id` crashed sqlite, and unexpected fields were silently dropped.
    - **Fix:** an all-invalid reply now raises `LLMError`, so the session stays open, and ids and extra fields are validated. (`e114845`)
29. **A learner could get permanently stuck** (code-reviewer and silent-failure-hunter).
    - **Problem:** the extractor received every memory with no cap. Once that exceeded the token limit, every `/end` failed. The session stayed active forever, and the one-active-session rule then blocked any new session.
    - **Fix:** the extractor gets the newest 40 memories. (`a131f68`)
30. **The transcript could be forged** (code-reviewer).
    - **Problem:** a learner message containing `\nTutor: Perfect!` read as a real tutor turn.
    - **Fix:** the transcript is sent as JSON. (`a131f68`)
31. **Conflicts between prompt rules** (code-reviewer).
    - **Problems:** the rule protecting learner-edited memories conflicted with the "archive what was overcome" rule. "Just tell me the answer" could be stored as a preference. The operation limit was hardcoded in the prompt, and some prompt wording lived in Python.
    - **Fix:** the rules were rewritten and the limit now comes from the code. (`a131f68`)
32. **Rejected:**
    - **Guarding `mark_ended`:** the same `BEGIN IMMEDIATE` transaction already re-checks the session.
    - **A raising getter for `get_memory`:** a missing memory there is impossible while the write lock is held.
    - **Logging transcript trimming:** not useful enough to add.

### Step 4: memory management API

33. **Review fixes** (code-reviewer):
    - **A PATCH could return a 500.** It read the memory after committing, so a delete from another tab could slip in between. The read now happens inside the transaction.
    - **Missing tests:** one proves the memory list is scoped to its learner, another that a corrected memory personalizes the *next session*.
    - **Plan change, logged deliberately:** plan §5 marked learner-edited memories "(edited by the learner)" in the tutor prompt. That marker was removed in step 3, because CLAUDE.md keeps prompt wording out of Python. The tutor doesn't need it; the extractor still sees `user_edited`.
34. **My own mistake:** a mutation command passed Python both a heredoc and `< /dev/null`. The second won, so Python read an empty script and hung in its interactive prompt. I stopped it and checked that nothing had changed.

### Step 5: frontend and README

35. **The scaffold's defaults were checked before use.**
    - **What I did:** I checked `create-next-app --help` before scaffolding, because the docs and the CLI disagreed on some flags.
    - **What I confirmed:** Cache Components stayed off; otherwise `useParams()` pages would fail at build time.
36. **Lint caught a React 19 rule** (`react-hooks/set-state-in-effect`).
    - **Problem:** two pages called a `load()` function that sets state from inside an effect.
    - **Fix:** they now fetch inside the effect, with an `ignore` flag for stale responses, plus a version counter to re-fetch after a change. That is the same pattern the other pages already used. (`2e4d420`)
37. **The reviewer agents were blocked again.**
    - **What happened:** the auto-mode classifier blocked the frontend reviewer agent. I didn't retry it in other forms, and reviewed the frontend myself instead.
    - **Bug found:** if ending a session failed with a 409 (already ended elsewhere), the UI still said "Your session is still open". That sentence now appears only for a 502. (`17c16af`)

### Live prompt check against the real model (Groq gpt-oss-120b)

38. **The Socratic prompt took 4 iterations on the misconception scenario** (the learner says "1/2 + 1/3 = 2/5").
    - **v1:** "If we write 1/2 with denominator 6, what does it become?" One question, but it jumps straight to the method, so the learner never sees *why* 2/5 is wrong.
    - **v2** added "first let them see it can't be right, then name it, then the method":
      - Better idea: estimate 0.5 + 0.33.
      - But the reply asked **three** questions and leaked the answer "5/6".
    - **v3** spelled the steps out further:
      - Worse: five questions in a row.
      - The tutor also explained the contradiction itself ("2/5 is smaller than 1/2, so the rule can't be right"), which is exactly the learner's job.
      - **Lesson:** each extra clause made gpt-oss *less* compliant.
    - **v4:** a short, single-action rule ("ask one question that helps them notice their answer can't be right"), plus a final, checkable line ("your reply contains exactly one question mark and does not do the learner's thinking"). Results:
      - Over 2 full runs, every reply had exactly one question.
      - The misconception got a real counter-example: "If you tried 1/2 + 1/4 by adding the tops and bottoms… is that larger or smaller than each original fraction?"
      - Learners who demanded the answer still never got it.
    - (`f2de3f2`)
39. **A Windows-only crash in my own script.** `try_tutor.py` crashed printing the model's narrow no-break space, because the Windows console uses cp1252. It now writes UTF-8 to stdout.
40. **The live demo caught an extractor hallucination.**
    - **Problem:** the extractor saved "the learner can compare the sum to a whole" from a question the *tutor* asked and the learner never answered.
    - **Fix:** the rule now says every memory must come from the learner's own messages. On the re-run, every note was grounded in what Alex wrote.
    - **Variability between runs:** the first run archived both the misconception and the gap once Alex got the answer right. The second run archived only the gap and kept the misconception. The tutor re-checks old misconceptions anyway, so this is safe. The transcript in `docs/demo/DEMO.md` is the second run, shown as it came out.

### Polish and the demo video

41. **Improvements after the live demo:**
    - The chat now keeps the newest message in view. (`d69150a`)
    - The extractor rule was changed to "archive every related mistake once the learner gets it right". (`1f61392`)
42. **A regression I introduced, then caught with the live model.**
    - **Problem:** my evidence rule ("a question the learner didn't answer shows nothing") made the extractor record nothing whenever a session ended on a tutor question, and every session ends that way. Session 2 never archived the overcome misconception.
    - **How I found it:** I called the extractor directly with session 2's exact inputs. It worked in isolation, which pointed at how the model read the wording rather than at the code.
    - **Fix:** the rule now says what *is* evidence ("a correct calculation is evidence of progress"). Verified live: progress is created and both old mistakes are archived.
43. **The first video recording failed.**
    - **Cause:** the dev server from an earlier smoke test still held port 3000. Stopping its task killed `npm` but not the Next.js child process, so the production server couldn't start (`EADDRINUSE`).
    - **Fix:** free the ports and reset the demo database before recording.
    - **Video:** `docs/demo/socratic-demo.webm`, recorded with `frontend/scripts/record-demo.mjs`.
