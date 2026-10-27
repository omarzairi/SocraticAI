"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorBanner, buttonClass, inputClass } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import type { Learner } from "@/lib/types";

export default function LearnerPicker() {
  const [learners, setLearners] = useState<Learner[] | null>(null);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0); // bumped after a change to re-fetch the list

  useEffect(() => {
    let ignore = false; // a response for a page we already left is dropped
    api
      .listLearners()
      .then((loaded) => !ignore && setLearners(loaded))
      .catch((err) => !ignore && setError(errorText(err)));
    return () => {
      ignore = true;
    };
  }, [version]);

  async function addLearner(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.createLearner(name);
      setName("");
      setVersion((current) => current + 1);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <h1 className="font-serif text-3xl">Who&apos;s learning today?</h1>
      <p className="mt-2 text-muted">
        Your tutor answers with questions and keeps notes on how you learn.
      </p>
      <ErrorBanner message={error} />

      {learners === null && !error && <p className="mt-6 text-muted">Loading…</p>}
      {learners?.length === 0 && (
        <p className="mt-6 text-muted">No learners yet. Add your name to start.</p>
      )}
      <ul className="mt-6 space-y-2">
        {learners?.map((learner) => (
          <li key={learner.id}>
            <Link
              href={`/learners/${learner.id}`}
              className="block rounded border border-line bg-card px-4 py-3 text-lg hover:border-tutor"
            >
              {learner.name}
            </Link>
          </li>
        ))}
      </ul>

      <form onSubmit={addLearner} className="mt-8 flex gap-2">
        <label htmlFor="name" className="sr-only">
          Your name
        </label>
        <input
          id="name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Your name"
          maxLength={60}
          className={inputClass}
        />
        <button type="submit" disabled={saving || !name.trim()} className={buttonClass}>
          Add learner
        </button>
      </form>
    </div>
  );
}
