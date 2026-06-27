"use client";

import { RoomContext } from "@livekit/components-react";
import LiveVoiceConversation from "@/app/components/LiveVoiceConversation";
import { useLiveKitSession } from "@/app/hooks/useLiveKitSession";

export default function LiveVoice() {
  const { state, connect, disconnect } = useLiveKitSession();

  if (state.status === "idle" || state.status === "error") {
    return (
      <Centered>
        {state.status === "error" && (
          <div className="w-full max-w-sm rounded-xl border border-red-300 bg-red-50 px-5 py-4 text-center text-sm text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">
            {state.message}
          </div>
        )}
        <p className="max-w-sm text-center text-sm text-zinc-500 dark:text-zinc-400">
          Talk to Sarjy hands-free. Press Connect, allow your mic, and just start
          speaking — turn-taking is automatic.
        </p>
        <button
          onClick={connect}
          className="rounded-full bg-blue-600 px-8 py-3 text-base font-semibold text-white shadow-lg shadow-blue-600/30 transition-all hover:bg-blue-500 hover:shadow-blue-500/40 active:scale-[0.97]"
        >
          {state.status === "error" ? "Try again" : "Connect"}
        </button>
      </Centered>
    );
  }

  if (state.status === "connecting") {
    return (
      <Centered>
        <Spinner />
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Connecting…</p>
      </Centered>
    );
  }

  return (
    <RoomContext.Provider value={state.room}>
      <div className="flex flex-col items-center gap-6">
        {state.status === "reconnecting" && (
          <div className="w-full max-w-sm rounded-xl border border-amber-300 bg-amber-50 px-4 py-2.5 text-center text-sm text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300">
            Reconnecting…
          </div>
        )}
        <LiveVoiceConversation />
        <button
          onClick={disconnect}
          className="rounded-full border border-zinc-300 px-6 py-2.5 text-sm font-medium text-zinc-600 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
        >
          Disconnect
        </button>
      </div>
    </RoomContext.Provider>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col items-center gap-5">{children}</div>;
}

function Spinner() {
  return (
    <span
      className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-300 border-t-blue-600 dark:border-zinc-700 dark:border-t-blue-500"
      aria-label="Loading"
    />
  );
}
