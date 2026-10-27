// Mirrors the response models in backend/app/schemas.py.

export type Learner = { id: number; name: string; created_at: string };

export type Session = {
  id: number;
  learner_id: number;
  topic: string;
  status: "active" | "ended";
  created_at: string;
  ended_at: string | null;
};

export type Message = {
  id: number;
  session_id: number;
  role: "learner" | "tutor";
  content: string;
  created_at: string;
};

export type SessionDetail = Session & { messages: Message[] };

export type ChatTurn = { learner_message: Message; tutor_message: Message };

export type MemoryKind = "progress" | "knowledge_gap" | "misconception" | "preference";

export type Memory = {
  id: number;
  learner_id: number;
  kind: MemoryKind;
  content: string;
  status: "active" | "archived";
  user_edited: boolean;
  source_session_id: number | null;
  created_at: string;
  updated_at: string;
};

export type MemoryUpdate = { created: Memory[]; updated: Memory[]; archived: Memory[] };

export type EndSessionResponse = { session: Session; memory_update: MemoryUpdate };

// One label per memory kind defined in backend/app/schemas.py (add new kinds here too).
export const MEMORY_KIND_LABELS: Record<MemoryKind, string> = {
  progress: "Progress",
  knowledge_gap: "Knowledge gaps",
  misconception: "Misconceptions",
  preference: "Learning preferences",
};
