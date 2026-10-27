"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ErrorBanner, LearnerNav, buttonClass, quietButtonClass } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { MEMORY_KIND_LABELS, type Memory, type MemoryKind } from "@/lib/types";

export default function MemoryPage() {
  const learnerId = Number(useParams<{ learnerId: string }>().learnerId);
  const [memories, setMemories] = useState<Memory[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0); // bumped after a change to re-fetch the list
  const reload = () => setVersion((current) => current + 1);

  useEffect(() => {
    let ignore = false; // a response for a page we already left is dropped
    api
      .listMemories(learnerId)
      .then((loaded) => !ignore && setMemories(loaded))
      .catch((err) => !ignore && setError(errorText(err)));
    return () => {
      ignore = true;
    };
  }, [learnerId, version]);

  const active = memories?.filter((memory) => memory.status === "active") ?? [];
  const archived = memories?.filter((memory) => memory.status === "archived") ?? [];
  const kinds = Object.keys(MEMORY_KIND_LABELS) as MemoryKind[];

  return (
    <div>
      <LearnerNav learnerId={learnerId} />
      <h1 className="font-serif text-3xl">What the tutor remembers</h1>
      <p className="mt-2 text-muted">
        Correct anything that&apos;s wrong. Notes you edit are kept exactly as you wrote them.
      </p>
      <ErrorBanner message={error} />
      {memories === null && !error && <p className="mt-6 text-muted">Loading…</p>}
      {memories?.length === 0 && (
        <p className="mt-6">Nothing yet. The tutor writes notes here when you end a session.</p>
      )}

      {kinds.map((kind) => {
        const ofKind = active.filter((memory) => memory.kind === kind);
        if (ofKind.length === 0) return null;
        return (
          <section key={kind} className="mt-8">
            <h2 className="font-serif text-xl">{MEMORY_KIND_LABELS[kind]}</h2>
            <ul className="mt-3 space-y-2">
              {ofKind.map((memory) => (
                <MemoryItem key={memory.id} memory={memory} onChange={reload} onError={setError} />
              ))}
            </ul>
          </section>
        );
      })}

      {archived.length > 0 && (
        <section className="mt-10">
          <h2 className="font-serif text-xl text-muted">No longer applies</h2>
          <ul className="mt-3 space-y-2 text-muted">
            {archived.map((memory) => (
              <MemoryItem key={memory.id} memory={memory} onChange={reload} onError={setError} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function MemoryItem({
  memory,
  onChange,
  onError,
}: {
  memory: Memory;
  onChange: () => void;
  onError: (message: string | null) => void;
}) {
  const [mode, setMode] = useState<"view" | "edit" | "confirm-delete">("view");
  const [content, setContent] = useState(memory.content);
  const [saving, setSaving] = useState(false);

  async function run(action: () => Promise<unknown>) {
    setSaving(true);
    onError(null);
    try {
      await action();
      setMode("view");
      onChange(); // re-fetch instead of patching local state
    } catch (err) {
      onError(errorText(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <li className="rounded border border-line bg-card px-4 py-3">
      {mode === "edit" ? (
        <div>
          <label htmlFor={`memory-${memory.id}`} className="sr-only">
            Memory text
          </label>
          <textarea
            id={`memory-${memory.id}`}
            value={content}
            onChange={(event) => setContent(event.target.value)}
            maxLength={300}
            rows={2}
            className="w-full rounded border border-line px-3 py-2 focus:border-tutor"
          />
          <div className="mt-2 flex gap-2">
            <button
              onClick={() => run(() => api.editMemory(memory.learner_id, memory.id, content))}
              disabled={saving || !content.trim()}
              className={buttonClass}
            >
              Save
            </button>
            <button onClick={() => setMode("view")} className={quietButtonClass}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="flex items-start justify-between gap-4">
          <p>
            {memory.content}
            {memory.user_edited && (
              <span className="ml-2 rounded bg-highlight px-1.5 text-sm text-ink">edited by you</span>
            )}
          </p>
          {mode === "confirm-delete" ? (
            <span className="flex shrink-0 gap-2">
              <button
                onClick={() => run(() => api.deleteMemory(memory.learner_id, memory.id))}
                disabled={saving}
                className={`${quietButtonClass} text-danger`}
              >
                Delete it
              </button>
              <button onClick={() => setMode("view")} className={quietButtonClass}>
                Keep
              </button>
            </span>
          ) : (
            <span className="flex shrink-0 gap-2">
              {memory.status === "active" && (
                <button onClick={() => setMode("edit")} className={quietButtonClass}>
                  Edit
                </button>
              )}
              <button onClick={() => setMode("confirm-delete")} className={quietButtonClass}>
                Delete
              </button>
            </span>
          )}
        </div>
      )}
    </li>
  );
}
