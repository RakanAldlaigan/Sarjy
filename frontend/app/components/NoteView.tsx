"use client";

import { NoteDetail } from "@/app/lib/api";

interface NoteViewProps {
  note: NoteDetail;
  onClose: () => void;
  onDelete: (noteId: string) => void;
}

function formatCreatedAt(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function NoteView({ note, onClose, onDelete }: NoteViewProps) {
  return (
    <div className="flex h-full min-h-0 w-full max-w-2xl flex-1 flex-col gap-4 overflow-y-auto rounded-2xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900/40">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <h2 className="text-lg font-semibold tracking-tight text-zinc-800 dark:text-zinc-100">
            {note.title}
          </h2>
          <p className="text-xs text-zinc-400 dark:text-zinc-500">{formatCreatedAt(note.createdAt)}</p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button
            onClick={() => onDelete(note.id)}
            className="rounded-xl px-3 py-1.5 text-sm font-medium text-zinc-500 transition-colors duration-150 hover:bg-red-500/10 hover:text-red-500 dark:text-zinc-400"
          >
            Delete
          </button>
          <button
            onClick={onClose}
            className="rounded-xl px-3 py-1.5 text-sm font-medium text-zinc-500 transition-colors duration-150 hover:bg-zinc-200 hover:text-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
          >
            Back to chat
          </button>
        </div>
      </div>
      <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-zinc-700 dark:text-zinc-200">
        {note.content}
      </p>
    </div>
  );
}
