"use client";

import { useCallback, useEffect, useState } from "react";
import ChatWindow, { ChatMessage } from "@/app/components/ChatWindow";
import SessionSidebar from "@/app/components/SessionSidebar";
import SignInScreen from "@/app/components/SignInScreen";
import VoiceInput from "@/app/components/VoiceInput";
import { useAuth } from "@/app/hooks/useAuth";
import { deleteSession, getSessionMessages, getSessions, SessionSummary, startNewSession } from "@/app/lib/api";
import { supabase } from "@/app/lib/supabase";

export default function Home() {
  const { session, loading } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [isBusy, setIsBusy] = useState(false);

  const refreshSessions = useCallback(async () => {
    try {
      setSessions(await getSessions());
    } catch {
      // sidebar list is best-effort
    }
  }, []);

  useEffect(() => {
    if (!session) {
      setMessages([]);
      setActiveSessionId(null);
      setSessions([]);
      return;
    }
    refreshSessions();
  }, [session?.user.id, refreshSessions]);

  const handleResult = useCallback(
    (transcript: string, reply: string, sessionId: string) => {
      setMessages((prev) => [
        ...prev,
        ...(transcript ? [{ role: "user" as const, content: transcript }] : []),
        { role: "assistant" as const, content: reply },
      ]);
      if (sessionId) {
        setActiveSessionId(sessionId);
        refreshSessions();
      }
    },
    [refreshSessions]
  );

  const handleSelectSession = useCallback(
    async (sessionId: string) => {
      if (sessionId === activeSessionId || isBusy) return;
      try {
        const history = await getSessionMessages(sessionId);
        setMessages(history);
        setActiveSessionId(sessionId);
      } catch {
        // ignore — sidebar selection is best-effort
      }
    },
    [activeSessionId, isBusy]
  );

  const handleDeleteSession = useCallback(
    async (sessionId: string) => {
      if (isBusy) return;
      try {
        await deleteSession(sessionId);
        if (sessionId === activeSessionId) {
          const newSessionId = await startNewSession();
          setMessages([]);
          setActiveSessionId(newSessionId);
        }
        refreshSessions();
      } catch {
        // ignore — user can retry
      }
    },
    [activeSessionId, isBusy, refreshSessions]
  );

  const handleNewSession = useCallback(async () => {
    if (isBusy) return;
    try {
      const sessionId = await startNewSession();
      setMessages([]);
      setActiveSessionId(sessionId);
      refreshSessions();
    } catch {
      // ignore — user can retry
    }
  }, [refreshSessions, isBusy]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white dark:bg-zinc-950">
        <p className="text-sm text-zinc-400 dark:text-zinc-500">Loading…</p>
      </div>
    );
  }

  if (!session) {
    return <SignInScreen />;
  }

  return (
    <div className="flex min-h-screen">
      <SessionSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
        onSignOut={() => supabase.auth.signOut()}
        canStartNewSession={sessions.find((s) => s.id === activeSessionId)?.isEmpty === false}
        disabled={isBusy}
      />
      <div className="flex flex-1 flex-col items-center gap-5 overflow-hidden px-8 py-6">
        <h1 className="text-xl font-semibold tracking-tight text-zinc-800 dark:text-zinc-100">Sarjy</h1>
        <ChatWindow messages={messages} />
        <VoiceInput sessionId={activeSessionId} onResult={handleResult} onBusyChange={setIsBusy} />
      </div>
    </div>
  );
}
