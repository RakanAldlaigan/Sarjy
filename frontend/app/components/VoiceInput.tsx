"use client";

import { useEffect, useRef, useState } from "react";
import { useVoiceRecorder } from "@/app/hooks/useVoiceRecorder";
import { playAudio } from "@/app/lib/audio";
import { ChatResult, sendAudioToChat } from "@/app/lib/api";
import { finishTurn, markAudioPlaying, startTurn } from "@/app/lib/timing";

interface VoiceInputProps {
  sessionId: string | null;
  onResult: (result: ChatResult) => void;
  onBusyChange?: (busy: boolean) => void;
}

export default function VoiceInput({ sessionId, onResult, onBusyChange }: VoiceInputProps) {
  const { isRecording, audioBlob, startRecording, stopRecording } = useVoiceRecorder();
  const [isProcessing, setIsProcessing] = useState(false);
  const recordingSessionIdRef = useRef<string | null>(null);

  useEffect(() => {
    onBusyChange?.(isRecording || isProcessing);
  }, [isRecording, isProcessing, onBusyChange]);

  useEffect(() => {
    if (!audioBlob) return;

    const process = async () => {
      setIsProcessing(true);
      const trace = startTurn();
      try {
        const result = await sendAudioToChat(audioBlob, recordingSessionIdRef.current, trace);
        onResult(result);

        if (result.audioBase64) {
          await playAudio(result.audioBase64, trace ? () => markAudioPlaying(trace) : undefined);
        }
      } catch {
        onResult({
          transcript: "",
          reply: "Sorry, something went wrong. Please try again.",
          audioBase64: "",
          sessionId: recordingSessionIdRef.current ?? "",
          pendingAction: null,
        });
      } finally {
        finishTurn(trace);
        setIsProcessing(false);
      }
    };

    process();
  }, [audioBlob, onResult]);

  const handleClick = () => {
    if (isRecording) {
      stopRecording();
    } else {
      recordingSessionIdRef.current = sessionId;
      startRecording();
    }
  };

  const label = isProcessing ? "Processing..." : isRecording ? "Stop Recording" : "Start Recording";

  return (
    <div className="flex flex-col items-center gap-3">
      <button
        onClick={handleClick}
        disabled={isProcessing}
        className={`rounded-full px-10 py-4 text-base font-semibold text-white shadow-lg transition-all duration-150 ease-out ${
          isRecording
            ? "bg-red-500 shadow-red-500/30 ring-4 ring-red-500/20 hover:bg-red-600"
            : isProcessing
            ? "cursor-not-allowed bg-zinc-200 text-zinc-400 shadow-none dark:bg-zinc-800 dark:text-zinc-600"
            : "bg-blue-600 shadow-blue-600/30 hover:bg-blue-500 hover:shadow-blue-500/40 active:scale-[0.97]"
        }`}
      >
        {label}
      </button>
      {isRecording && (
        <span className="flex items-center gap-2 text-sm text-red-500">
          <span className="h-2 w-2 animate-pulse rounded-full bg-red-500" />
          Recording...
        </span>
      )}
    </div>
  );
}
