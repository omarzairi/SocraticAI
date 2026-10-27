"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ErrorBanner, LearnerNav, buttonClass, quietButtonClass } from "@/components/ui";
import { ApiError, api, errorText } from "@/lib/api";
import { MEMORY_KIND_LABELS, type MemoryUpdate, type SessionDetail } from "@/lib/types";

export default function ChatPage() {
  const params = useParams<{ learnerId: string; sessionId: string }>();
  const learnerId = Number(params.learnerId);
  const sessionId = Number(params.sessionId);
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState<"sending" | "ending" | null>(null);
  const [memoryUpdate, setMemoryUpdate] = useState<MemoryUpdate | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    api
      .getSession(learnerId, sessionId)
      .then((loaded) => !ignore && setSession(loaded))
      .catch((err) => !ignore && setError(errorText(err)));
    return () => {
      ignore = true;
    };
  }, [learnerId, sessionId]);

  async function send(event?: React.FormEvent) {
    event?.preventDefault();
    if (!session || !draft.trim() || busy) return;
    setBusy("sending");
    setError(null);
    try {
      const turn = await api.sendMessage(learnerId, sessionId, draft);
      setSession({ ...session, messages: [...session.messages, turn.learner_message, turn.tutor_message] });
      setDraft(""); // cleared only on success, so a failed message can be sent again
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function endSession() {
    setBusy("ending");
    setError(null);
    try {
      const result = await api.endSession(learnerId, sessionId);
      setSession(await api.getSession(learnerId, sessionId));
      setMemoryUpdate(result.memory_update);
    } catch (err) {
      // 502: the memory update failed and nothing changed, so the learner can simply retry.
      const stillOpen = err instanceof ApiError && err.status === 502;
      setError(stillOpen ? `${errorText(err)} Your session is still open.` : errorText(err));
    } finally {
      setBusy(null);
    }
  }

  if (!session) {
    return (
      <div>
        <LearnerNav learnerId={learnerId} />
        <ErrorBanner message={error} />
        {!error && <p className="text-muted">Loading…</p>}
      </div>
    );
  }

  const isActive = session.status === "active";
  return (
    <div>
      <LearnerNav learnerId={learnerId} />
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="font-serif text-3xl">{session.topic}</h1>
        {isActive && (
          <button onClick={endSession} disabled={busy !== null} className={quietButtonClass}>
            {busy === "ending" ? "Updating memory…" : "End session"}
          </button>
        )}
      </div>

      <ol className="mt-6 space-y-5">
        {session.messages.map((message) =>
          message.role === "tutor" ? (
            <li
              key={message.id}
              className="whitespace-pre-wrap border-l-4 border-tutor pl-4 font-serif text-lg leading-relaxed"
            >
              {message.content}
            </li>
          ) : (
            <li
              key={message.id}
              className="ml-auto max-w-[85%] whitespace-pre-wrap rounded border border-line bg-card px-4 py-3"
            >
              {message.content}
            </li>
          ),
        )}
        {busy === "sending" && <li className="pl-5 text-muted">Tutor is thinking…</li>}
      </ol>

      <ErrorBanner message={error} />
      {memoryUpdate && <MemoryUpdateCard learnerId={learnerId} update={memoryUpdate} />}

      {isActive ? (
        <form onSubmit={send} className="mt-6">
          <label htmlFor="message" className="sr-only">
            Your answer
          </label>
          <textarea
            id="message"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                send();
              }
            }}
            rows={3}
            maxLength={2000}
            disabled={busy !== null}
            placeholder="Think out loud. Enter sends, Shift+Enter adds a line."
            className="w-full rounded border border-line bg-card px-3 py-2 placeholder:text-muted focus:border-tutor"
          />
          <button type="submit" disabled={busy !== null || !draft.trim()} className={`${buttonClass} mt-2`}>
            Send
          </button>
        </form>
      ) : (
        <p className="mt-8 text-muted">
          This session has ended.{" "}
          <Link href={`/learners/${learnerId}`} className="text-tutor hover:underline">
            Start a new session
          </Link>
        </p>
      )}
    </div>
  );
}

function MemoryUpdateCard({ learnerId, update }: { learnerId: number; update: MemoryUpdate }) {
  const notes = [
    ...update.created.map((memory) => ({ memory, change: "New" })),
    ...update.updated.map((memory) => ({ memory, change: "Updated" })),
    ...update.archived.map((memory) => ({ memory, change: "No longer applies" })),
  ];
  return (
    <section className="mt-8 rounded bg-highlight px-5 py-4">
      <h2 className="font-serif text-xl">What I learned about you</h2>
      {notes.length === 0 ? (
        <p className="mt-2">Nothing new to remember from this session.</p>
      ) : (
        <ul className="mt-2 space-y-1">
          {notes.map(({ memory, change }) => (
            <li key={`${change}-${memory.id}`}>
              <span className="font-medium">{change}</span> ({MEMORY_KIND_LABELS[memory.kind]}):{" "}
              {memory.content}
            </li>
          ))}
        </ul>
      )}
      <Link href={`/learners/${learnerId}/memory`} className="mt-3 inline-block underline">
        Review or correct these notes
      </Link>
    </section>
  );
}
