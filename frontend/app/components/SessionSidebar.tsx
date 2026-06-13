"use client";

import { SessionSummary } from "@/app/lib/api";

interface SessionSidebarProps {
  sessions: SessionSummary[];
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
  onDeleteSession: (sessionId: string) => void;
  canStartNewSession: boolean;
  disabled: boolean;
}

export default function SessionSidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  canStartNewSession,
  disabled,
}: SessionSidebarProps) {
  const newSessionEnabled = canStartNewSession && !disabled;

  return (
    <aside className="flex h-screen w-64 flex-col gap-4 border-r border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <h2 className="px-1 text-xs font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
        Sessions
      </h2>

      <button
        onClick={onNewSession}
        disabled={!newSessionEnabled}
        className={`rounded-xl px-3 py-2 text-sm font-medium transition-colors duration-150 ${
          newSessionEnabled
            ? "bg-blue-600 text-white shadow-sm hover:bg-blue-500"
            : "cursor-not-allowed bg-zinc-200 text-zinc-400 dark:bg-zinc-800 dark:text-zinc-600"
        }`}
      >
        New session
      </button>

      <div className="flex flex-col gap-1 overflow-y-auto">
        {sessions.length === 0 && (
          <p className="px-2 text-sm text-zinc-400">No past sessions yet</p>
        )}
        {sessions.map((session) => (
          <div key={session.id} className="group flex items-center gap-1">
            <button
              onClick={() => onSelectSession(session.id)}
              disabled={disabled}
              className={`min-w-0 flex-1 truncate rounded-xl px-3 py-2 text-left text-sm transition-colors duration-150 ${
                disabled
                  ? "cursor-not-allowed text-zinc-400 dark:text-zinc-600"
                  : session.id === activeSessionId
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-zinc-700 hover:bg-zinc-200 dark:text-zinc-300 dark:hover:bg-zinc-800"
              }`}
            >
              {session.isEmpty ? "New session" : session.preview || "Untitled session"}
            </button>
            <button
              onClick={() => onDeleteSession(session.id)}
              disabled={disabled}
              aria-label="Delete session"
              className={`rounded-lg p-1.5 transition-colors duration-150 ${
                disabled
                  ? "cursor-not-allowed text-zinc-300 dark:text-zinc-700"
                  : "text-zinc-400 opacity-0 hover:bg-red-500/10 hover:text-red-500 group-hover:opacity-100 dark:text-zinc-500"
              }`}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-4 w-4"
              >
                <path d="M4 5.5h12" />
                <path d="M7.5 5.5V4a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v1.5" />
                <path d="M5.5 5.5 6 16a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1l.5-10.5" />
                <path d="M8.5 8.5v5" />
                <path d="M11.5 8.5v5" />
              </svg>
            </button>
          </div>
        ))}
      </div>
    </aside>
  );
}
