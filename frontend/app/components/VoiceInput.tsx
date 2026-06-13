"use client";

import { useEffect, useState } from "react";
import { useVoiceRecorder } from "@/app/hooks/useVoiceRecorder";
import { sendAudioToChat } from "@/app/lib/api";

interface VoiceInputProps {
  onResult: (transcript: string, reply: string) => void;
}

export default function VoiceInput({ onResult }: VoiceInputProps) {
  const { isRecording, audioBlob, startRecording, stopRecording } = useVoiceRecorder();
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    if (!audioBlob) return;

    const process = async () => {
      setIsProcessing(true);
      try {
        const { transcript, reply, audioBase64 } = await sendAudioToChat(audioBlob);
        onResult(transcript, reply);

        if (audioBase64) {
          const audio = new Audio(`data:audio/mpeg;base64,${audioBase64}`);
          await audio.play();
        }
      } catch {
        onResult("", "Sorry, something went wrong. Please try again.");
      } finally {
        setIsProcessing(false);
      }
    };

    process();
  }, [audioBlob, onResult]);

  const handleClick = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  const label = isProcessing ? "Processing..." : isRecording ? "Stop Recording" : "Start Recording";

  return (
    <button
      onClick={handleClick}
      disabled={isProcessing}
      className={`px-6 py-3 rounded-full font-medium text-white transition-colors ${
        isRecording
          ? "bg-red-500 hover:bg-red-600"
          : isProcessing
          ? "bg-gray-400 cursor-not-allowed"
          : "bg-blue-500 hover:bg-blue-600"
      }`}
    >
      {label}
    </button>
  );
}
