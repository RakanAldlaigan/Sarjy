import { ChatMessage } from "@/app/components/ChatWindow";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface ChatResult {
  transcript: string;
  reply: string;
  audioBase64: string;
  sessionId: string;
}

export async function sendAudioToChat(audioBlob: Blob, sessionId?: string | null): Promise<ChatResult> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.webm");
  if (sessionId) {
    formData.append("session_id", sessionId);
  }

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
    sessionId: data.session_id,
  };
}

export interface SessionSummary {
  id: string;
  preview: string;
  isEmpty: boolean;
}

export async function getSessions(): Promise<SessionSummary[]> {
  const response = await fetch(`${API_BASE_URL}/sessions`);

  if (!response.ok) {
    throw new Error(`Failed to fetch sessions: ${response.status}`);
  }

  const data = await response.json();
  return data.map(
    (session: { id: string; preview: string; is_empty: boolean }) => ({
      id: session.id,
      preview: session.preview,
      isEmpty: session.is_empty,
    })
  );
}

export async function getSessionMessages(sessionId: string): Promise<ChatMessage[]> {
  const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/messages`);

  if (!response.ok) {
    throw new Error(`Failed to fetch session messages: ${response.status}`);
  }

  return response.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}`, { method: "DELETE" });

  if (!response.ok) {
    throw new Error(`Failed to delete session: ${response.status}`);
  }
}

export async function startNewSession(): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/sessions/new`, { method: "POST" });

  if (!response.ok) {
    throw new Error(`Failed to create session: ${response.status}`);
  }

  const data = await response.json();
  return data.session_id;
}
