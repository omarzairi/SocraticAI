"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ErrorBanner, LearnerNav, buttonClass, inputClass } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import type { Learner, Session } from "@/lib/types";

export default function SessionsPage() {
  const learnerId = Number(useParams<{ learnerId: string }>().learnerId);
  const router = useRouter();
  const [learner, setLearner] = useState<Learner | null>(null);
  const [sessions, setSessions] = useState<Session[] | null>(null);
  const [topic, setTopic] = useState("");
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false; // a response for a page we already left is dropped
    Promise.all([api.getLearner(learnerId), api.listSessions(learnerId)])
      .then(([loadedLearner, loadedSessions]) => {
        if (ignore) return;
        setLearner(loadedLearner);
        setSessions(loadedSessions);
      })
      .catch((err) => !ignore && setError(errorText(err)));
    return () => {
      ignore = true;
    };
  }, [learnerId]);

  async function startSession(event: React.FormEvent) {
    event.preventDefault();
    setStarting(true);
    setError(null);
    try {
      const session = await api.startSession(learnerId, topic);
      router.push(`/learners/${learnerId}/sessions/${session.id}`);
    } catch (err) {
      setError(errorText(err));
      setStarting(false);
    }
  }

  const active = sessions?.find((session) => session.status === "active");
  const ended = sessions?.filter((session) => session.status === "ended") ?? [];

  return (
    <div>
      <LearnerNav learnerId={learnerId} />
      <h1 className="font-serif text-3xl">{learner ? `Hi ${learner.name}` : "Your sessions"}</h1>
      <ErrorBanner message={error} />
      {sessions === null && !error && <p className="mt-6 text-muted">Loading…</p>}

      {sessions && active && (
        <section className="mt-6 rounded border border-tutor/40 bg-tutor-soft px-4 py-4">
          <p>
            You have a session in progress on <strong>{active.topic}</strong>.
          </p>
          <Link
            href={`/learners/${learnerId}/sessions/${active.id}`}
            className={`${buttonClass} mt-3 inline-block`}
          >
            Continue session
          </Link>
        </section>
      )}

      {sessions && !active && (
        <form onSubmit={startSession} className="mt-6">
          <label htmlFor="topic" className="block font-medium">
            What do you want to explore?
          </label>
          <div className="mt-2 flex gap-2">
            <input
              id="topic"
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
              placeholder="For example: adding fractions"
              maxLength={120}
              className={inputClass}
            />
            <button type="submit" disabled={starting || !topic.trim()} className={buttonClass}>
              {starting ? "Starting…" : "Start session"}
            </button>
          </div>
        </form>
      )}

      {ended.length > 0 && (
        <section className="mt-10">
          <h2 className="font-serif text-xl">Past sessions</h2>
          <ul className="mt-3 space-y-2">
            {ended.map((session) => (
              <li key={session.id}>
                <Link
                  href={`/learners/${learnerId}/sessions/${session.id}`}
                  className="flex justify-between rounded border border-line bg-card px-4 py-3 hover:border-tutor"
                >
                  <span>{session.topic}</span>
                  <span className="text-sm text-muted">
                    {new Date(session.created_at).toLocaleDateString()}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
