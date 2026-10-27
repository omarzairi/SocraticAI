-- Ids use AUTOINCREMENT so a deleted row's id is never reused.
-- Timestamps are UTC ISO-8601 strings written by the application.

CREATE TABLE IF NOT EXISTS learners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id INTEGER NOT NULL REFERENCES learners (id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'ended')),
    created_at TEXT NOT NULL,
    ended_at TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions (id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('learner', 'tutor')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- kind is validated in Python (app/schemas.py) so a new kind needs no schema change.
-- user_edited = 1 means the learner changed this memory; the extractor must never touch it.
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id INTEGER NOT NULL REFERENCES learners (id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    user_edited INTEGER NOT NULL DEFAULT 0 CHECK (user_edited IN (0, 1)),
    source_session_id INTEGER REFERENCES sessions (id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_learner ON sessions (learner_id);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages (session_id);
CREATE INDEX IF NOT EXISTS idx_memories_learner ON memories (learner_id);
