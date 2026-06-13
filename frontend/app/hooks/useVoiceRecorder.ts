"use client";

import { useCallback, useRef, useState } from "react";

const MAX_RECORDING_MS = 60_000;

interface UseVoiceRecorder {
  isRecording: boolean;
  audioBlob: Blob | null;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
}

export function useVoiceRecorder(): UseVoiceRecorder {
  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop();
  }, []);

  const startRecording = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
    chunksRef.current = [];

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };

    recorder.onstop = () => {
      stream.getTracks().forEach((track) => track.stop());
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      setAudioBlob(new Blob(chunksRef.current, { type: "audio/webm" }));
      setIsRecording(false);
    };

    recorder.start();
    mediaRecorderRef.current = recorder;
    setAudioBlob(null);
    setIsRecording(true);

    timeoutRef.current = setTimeout(stopRecording, MAX_RECORDING_MS);
  }, [stopRecording]);

  return { isRecording, audioBlob, startRecording, stopRecording };
}
