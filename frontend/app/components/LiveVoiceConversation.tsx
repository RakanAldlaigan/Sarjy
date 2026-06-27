"use client";

import {
  BarVisualizer,
  RoomAudioRenderer,
  useVoiceAssistant,
} from "@livekit/components-react";
import { useEffect, useState } from "react";

const AGENT_PRESENCE_TIMEOUT_MS = 8000;

const ACTIVE_AGENT_STATES = new Set(["idle", "listening", "thinking", "speaking"]);

export default function LiveVoiceConversation() {
  const { state, audioTrack, agent } = useVoiceAssistant();
  const [agentTimedOut, setAgentTimedOut] = useState(false);

  const agentPresent = agent !== undefined && ACTIVE_AGENT_STATES.has(state);

  const [wasAgentPresent, setWasAgentPresent] = useState(agentPresent);
  if (agentPresent !== wasAgentPresent) {
    setWasAgentPresent(agentPresent);
    if (agentPresent) setAgentTimedOut(false);
  }

  useEffect(() => {
    if (agentPresent) return;
    const timer = setTimeout(() => setAgentTimedOut(true), AGENT_PRESENCE_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [agentPresent]);

  const status = describeStatus(state, agentPresent);

  return (
    <div className="flex flex-col items-center gap-8">
      <RoomAudioRenderer />

      <div className="flex h-40 w-full max-w-sm items-center justify-center">
        <BarVisualizer
          state={state}
          barCount={5}
          trackRef={audioTrack}
          className="flex h-24 items-center gap-1.5"
          options={{ minHeight: 8 }}
        />
      </div>

      <div className="flex flex-col items-center gap-2 text-center">
        <span className="flex items-center gap-2 text-base font-medium text-zinc-700 dark:text-zinc-200">
          <span
            className={`h-2.5 w-2.5 rounded-full ${status.dotClass}`}
            aria-hidden="true"
          />
          {status.label}
        </span>
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Hands-free — just start talking. Press Disconnect when you&apos;re done.
        </p>
      </div>

      {agentTimedOut && !agentPresent && (
        <div className="w-full max-w-sm rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-center text-sm text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300">
          Couldn&apos;t reach the assistant. Make sure the agent worker is running —
          it&apos;ll retry on its own.
        </div>
      )}
    </div>
  );
}

function describeStatus(
  state: string,
  agentPresent: boolean
): { label: string; dotClass: string } {
  if (!agentPresent) {
    return { label: "Connecting to the assistant…", dotClass: "animate-pulse bg-zinc-400" };
  }
  switch (state) {
    case "listening":
      return { label: "Listening", dotClass: "bg-green-500" };
    case "thinking":
      return { label: "Thinking…", dotClass: "animate-pulse bg-amber-500" };
    case "speaking":
      return { label: "Speaking", dotClass: "bg-blue-500" };
    default:
      return { label: "Ready", dotClass: "bg-zinc-400" };
  }
}
