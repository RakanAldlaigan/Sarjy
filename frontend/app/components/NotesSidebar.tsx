"use client";

import CalendarConnect from "@/app/components/CalendarConnect";
import { NoteSummary } from "@/app/lib/api";

interface NotesSidebarProps {
  notes: NoteSummary[];
  activeNoteId: string | null;
  onSelectNote: (noteId: string) => void;
  onSignOut: () => void;
}

export default function NotesSidebar({
  notes,
  activeNoteId,
  onSelectNote,
  onSignOut,
}: NotesSidebarProps) {
  return (
    <aside className="flex h-screen w-64 flex-col gap-4 border-r border-zinc-200 bg-zinc-50 p-4 pt-6 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex flex-1 flex-col gap-5 overflow-y-auto">
        <section className="flex flex-col gap-1">
          <h2 className="px-1 pb-1 text-xs font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
            Notes
          </h2>
          {notes.length === 0 && <p className="px-2 text-sm text-zinc-400">No notes yet</p>}
          {notes.map((note) => (
            <button
              key={note.id}
              onClick={() => onSelectNote(note.id)}
              className={`min-w-0 truncate rounded-xl px-3 py-2 text-left text-sm transition-colors duration-150 ${
                note.id === activeNoteId
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-zinc-700 hover:bg-zinc-200 dark:text-zinc-300 dark:hover:bg-zinc-800"
              }`}
            >
              {note.title || "Untitled note"}
            </button>
          ))}
        </section>
      </div>

      <CalendarConnect />

      <button
        onClick={onSignOut}
        className="rounded-xl bg-red-500/10 px-3 py-2 text-sm font-medium text-red-600 transition-colors duration-150 hover:bg-red-500/20 dark:text-red-400"
      >
        Sign out
      </button>
    </aside>
  );
}
