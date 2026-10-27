import type {
  ChatTurn,
  EndSessionResponse,
  Learner,
  Memory,
  Session,
  SessionDetail,
} from "./types";

// 127.0.0.1 rather than localhost: on Windows "localhost" can resolve to IPv6 first.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init.headers },
    });
  } catch {
    // Also what an unexpected server crash looks like: a 500 carries no CORS headers.
    throw new ApiError(
      0,
      `Can't reach the server at ${API_BASE_URL}, or it failed unexpectedly. Is the backend running?`,
    );
  }
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response));
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

// FastAPI sends {"detail": "..."} for our errors and {"detail": [{msg}, ...]} for validation.
async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail.map((error: { msg?: string }) => error.msg).join(" ");
    }
  } catch {
    // The body wasn't JSON; fall through to the generic message.
  }
  return `The server answered with an error (${response.status}).`;
}

const learnerPath = (learnerId: number) => `/api/learners/${learnerId}`;
const sessionPath = (learnerId: number, sessionId: number) =>
  `${learnerPath(learnerId)}/sessions/${sessionId}`;
const post = (body?: unknown): RequestInit => ({
  method: "POST",
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const api = {
  listLearners: () => request<Learner[]>("/api/learners"),
  createLearner: (name: string) => request<Learner>("/api/learners", post({ name })),
  getLearner: (learnerId: number) => request<Learner>(learnerPath(learnerId)),

  listSessions: (learnerId: number) => request<Session[]>(`${learnerPath(learnerId)}/sessions`),
  startSession: (learnerId: number, topic: string) =>
    request<SessionDetail>(`${learnerPath(learnerId)}/sessions`, post({ topic })),
  getSession: (learnerId: number, sessionId: number) =>
    request<SessionDetail>(sessionPath(learnerId, sessionId)),
  sendMessage: (learnerId: number, sessionId: number, content: string) =>
    request<ChatTurn>(`${sessionPath(learnerId, sessionId)}/messages`, post({ content })),
  endSession: (learnerId: number, sessionId: number) =>
    request<EndSessionResponse>(`${sessionPath(learnerId, sessionId)}/end`, post()),

  listMemories: (learnerId: number) => request<Memory[]>(`${learnerPath(learnerId)}/memories`),
  editMemory: (learnerId: number, memoryId: number, content: string) =>
    request<Memory>(`${learnerPath(learnerId)}/memories/${memoryId}`, {
      method: "PATCH",
      body: JSON.stringify({ content }),
    }),
  deleteMemory: (learnerId: number, memoryId: number) =>
    request<void>(`${learnerPath(learnerId)}/memories/${memoryId}`, { method: "DELETE" }),
};

export function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}
