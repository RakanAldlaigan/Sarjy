"use client";

import { useState } from "react";
import { playAudio } from "@/app/lib/audio";
import { PendingAction, sendPendingAction } from "@/app/lib/api";

interface PendingActionCardProps {
  sessionId: string;
  pendingAction: PendingAction;
  onResolved: (reply: string) => void;
}

export default function PendingActionCard({ sessionId, pendingAction, onResolved }: PendingActionCardProps) {
  const [busy, setBusy] = useState(false);

  const respond = async (action: "confirm" | "cancel") => {
    if (busy) return;
    setBusy(true);
    try {
      const result = await sendPendingAction(sessionId, action);
      onResolved(result.reply);
      if (result.audioBase64) {
        await playAudio(result.audioBase64);
      }
    } catch {
      onResolved("Sorry, something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex w-full max-w-2xl flex-col gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm dark:border-amber-500/40 dark:bg-amber-500/10">
      <p className="text-zinc-800 dark:text-zinc-100">{pendingAction.summary}</p>
      {pendingAction.conflictWarning && (
        <p className="text-amber-700 dark:text-amber-400">{pendingAction.conflictWarning}</p>
      )}
      <div className="flex justify-end gap-2">
        <button
          onClick={() => respond("cancel")}
          disabled={busy}
          className="rounded-xl px-4 py-2 text-sm font-medium text-zinc-600 transition-colors duration-150 hover:bg-zinc-200 disabled:opacity-50 dark:text-zinc-300 dark:hover:bg-zinc-800"
        >
          Cancel
        </button>
        <button
          onClick={() => respond("confirm")}
          disabled={busy}
          className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors duration-150 hover:bg-blue-500 disabled:opacity-50"
        >
          Confirm
        </button>
      </div>
    </div>
  );
}
