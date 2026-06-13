const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface ChatResult {
  transcript: string;
  reply: string;
  audioBase64: string;
}

export async function sendAudioToChat(audioBlob: Blob): Promise<ChatResult> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.webm");

  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.status}`);
  }

  const data = await response.json();
  return {
    transcript: data.transcript,
    reply: data.reply,
    audioBase64: data.audio_base64,
  };
}
