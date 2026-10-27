import Link from "next/link";

export function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="my-4 rounded border border-danger/40 bg-danger/5 px-4 py-3 text-danger">
      {message}
    </p>
  );
}

export function LearnerNav({ learnerId }: { learnerId: number }) {
  return (
    <nav className="mb-6 flex gap-5 text-sm">
      <Link href={`/learners/${learnerId}`} className="text-tutor hover:underline">
        Sessions
      </Link>
      <Link href={`/learners/${learnerId}/memory`} className="text-tutor hover:underline">
        What the tutor remembers
      </Link>
      <Link href="/" className="text-muted hover:underline">
        Switch learner
      </Link>
    </nav>
  );
}

export const buttonClass =
  "shrink-0 whitespace-nowrap rounded bg-tutor px-4 py-2 font-medium text-white hover:bg-tutor/90 disabled:opacity-50";
export const quietButtonClass =
  "rounded border border-line bg-card px-3 py-1.5 text-sm hover:border-tutor disabled:opacity-50";
export const inputClass =
  "w-full rounded border border-line bg-card px-3 py-2 placeholder:text-muted focus:border-tutor";
