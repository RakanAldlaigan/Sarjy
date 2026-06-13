"use client";

import { useCallback, useState } from "react";
import VoiceInput from "@/app/components/VoiceInput";

export default function Home() {
  const [transcript, setTranscript] = useState("");
  const [reply, setReply] = useState("");

  const handleResult = useCallback((t: string, r: string) => {
    setTranscript(t);
    setReply(r);
  }, []);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-2xl font-semibold">Sarjy</h1>
      <VoiceInput onResult={handleResult} />
      {(transcript || reply) && (
        <div className="w-full max-w-md space-y-2 text-sm">
          {transcript && <p><span className="font-medium">You:</span> {transcript}</p>}
          {reply && <p><span className="font-medium">Sarjy:</span> {reply}</p>}
        </div>
      )}
    </div>
  );
}
