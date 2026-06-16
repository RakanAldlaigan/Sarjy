import { ChatMessage } from "@/app/components/ChatWindow";
import { supabase } from "@/app/lib/supabase";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function getAuthHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface PendingAction {
  actionType: string;
  summary: string;
  conflictWarning: string | null;
}

interface PendingActionPayload {
  action_type: string;
  summary: string;
  conflict_warning: string | null;
}

function mapPendingAction(payload?: PendingActionPayload | null): PendingAction | null {
  if (!payload) return null;
  return {
    actionType: payload.action_type,
    summary: payload.summary,
    conflictWarning: payload.conflict_warning,
  };
}

export interface ChatResult {
  transcript: string;
  reply: string;
  audioBase64: string;
  sessionId: string;
  pendingAction: PendingAction | null;
}

export async function sendAudioToChat(audioBlob: Blob, sessionId?: string | null): Promise<ChatResult> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.webm");
  if (sessionId) {
    formData.append("session_id", sessionId);
  }
  formData.append("timezone", Intl.DateTimeFormat().resolvedOptions().timeZone);

  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: await getAuthHeaders(),
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
    pendingAction: mapPendingAction(data.pending_action),
  };
}

export async function sendPendingAction(sessionId: string, action: "confirm" | "cancel"): Promise<ChatResult> {
  const response = await fetch(`${API_BASE_URL}/chat/pending-action`, {
    method: "POST",
    headers: { ...(await getAuthHeaders()), "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, action }),
  });

  if (!response.ok) {
    throw new Error(`Failed to send pending action: ${response.status}`);
  }

  const data = await response.json();
  return {
    transcript: data.transcript,
    reply: data.reply,
    audioBase64: data.audio_base64,
    sessionId: data.session_id,
    pendingAction: mapPendingAction(data.pending_action),
  };
}

export async function getPendingAction(sessionId: string): Promise<PendingAction | null> {
  const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/pending-action`, {
    headers: await getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch pending action: ${response.status}`);
  }

  const data = await response.json();
  return mapPendingAction(data);
}

export async function getCalendarStatus(): Promise<boolean> {
  const response = await fetch(`${API_BASE_URL}/calendar/status`, { headers: await getAuthHeaders() });

  if (!response.ok) {
    throw new Error(`Failed to fetch calendar status: ${response.status}`);
  }

  const data = await response.json();
  return data.connected;
}

export async function getCalendarConnectUrl(): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/calendar/connect`, { headers: await getAuthHeaders() });

  if (!response.ok) {
    throw new Error(`Failed to get calendar connect URL: ${response.status}`);
  }

  const data = await response.json();
  return data.authorization_url;
}

export async function disconnectCalendar(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/calendar/disconnect`, {
    method: "DELETE",
    headers: await getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Failed to disconnect calendar: ${response.status}`);
  }
}

export interface NoteSummary {
  id: string;
  title: string;
  createdAt: string;
}

export interface NoteDetail extends NoteSummary {
  content: string;
}

export interface SessionSummary {
  id: string;
  preview: string;
  isEmpty: boolean;
}

export async function getSessions(): Promise<SessionSummary[]> {
  const response = await fetch(`${API_BASE_URL}/sessions`, { headers: await getAuthHeaders() });

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
  const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/messages`, {
    headers: await getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch session messages: ${response.status}`);
  }

  return response.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}`, {
    method: "DELETE",
    headers: await getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Failed to delete session: ${response.status}`);
  }
}

export async function getNotes(): Promise<NoteSummary[]> {
  const response = await fetch(`${API_BASE_URL}/notes`, { headers: await getAuthHeaders() });

  if (!response.ok) {
    throw new Error(`Failed to fetch notes: ${response.status}`);
  }

  const data = await response.json();
  return data.map((note: { id: string; title: string; created_at: string }) => ({
    id: note.id,
    title: note.title,
    createdAt: note.created_at,
  }));
}

export async function getNote(noteId: string): Promise<NoteDetail> {
  const response = await fetch(`${API_BASE_URL}/notes/${noteId}`, { headers: await getAuthHeaders() });

  if (!response.ok) {
    throw new Error(`Failed to fetch note: ${response.status}`);
  }

  const data = await response.json();
  return {
    id: data.id,
    title: data.title,
    content: data.content,
    createdAt: data.created_at,
  };
}

export async function deleteNote(noteId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/notes/${noteId}`, {
    method: "DELETE",
    headers: await getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Failed to delete note: ${response.status}`);
  }
}

export async function startNewSession(): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/sessions/new`, {
    method: "POST",
    headers: await getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Failed to create session: ${response.status}`);
  }

  const data = await response.json();
  return data.session_id;
}
