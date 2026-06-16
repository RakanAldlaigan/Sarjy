"use client";

import { useCallback, useEffect, useState } from "react";
import ChatWindow, { ChatMessage } from "@/app/components/ChatWindow";
import NoteView from "@/app/components/NoteView";
import PendingActionCard from "@/app/components/PendingActionCard";
import SessionSidebar from "@/app/components/SessionSidebar";
import SignInScreen from "@/app/components/SignInScreen";
import VoiceInput from "@/app/components/VoiceInput";
import { useAuth } from "@/app/hooks/useAuth";
import {
  ChatResult,
  deleteNote,
  deleteSession,
  getNote,
  getNotes,
  getPendingAction,
  getSessionMessages,
  getSessions,
  NoteDetail,
  NoteSummary,
  PendingAction,
  SessionSummary,
  startNewSession,
} from "@/app/lib/api";
import { supabase } from "@/app/lib/supabase";

export default function Home() {
  const { session, loading } = useAuth();

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

  // Keying by user id remounts the app on sign-in/out and user switch, so all
  // session state resets cleanly via unmount rather than a reset effect.
  return <SarjyApp key={session.user.id} />;
}

function SarjyApp() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [isBusy, setIsBusy] = useState(false);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [notes, setNotes] = useState<NoteSummary[]>([]);
  const [activeNote, setActiveNote] = useState<NoteDetail | null>(null);

  const refreshSessions = useCallback(async () => {
    try {
      setSessions(await getSessions());
    } catch {
      // sidebar list is best-effort
    }
  }, []);

  const refreshNotes = useCallback(async () => {
    try {
      setNotes(await getNotes());
    } catch {
      // notes list is best-effort
    }
  }, []);

  useEffect(() => {
    // On mount, resume the most recent session and re-render its pending-action card
    // if one is still live (the backend silently clears expired ones).
    let cancelled = false;
    (async () => {
      let list: SessionSummary[];
      try {
        list = await getSessions();
      } catch {
        return;
      }
      if (cancelled) return;
      setSessions(list);

      const mostRecent = list[0];
      if (!mostRecent) return;
      try {
        const history = await getSessionMessages(mostRecent.id);
        if (cancelled) return;
        setMessages(history);
        setActiveSessionId(mostRecent.id);
      } catch {
        return;
      }
      try {
        const pending = await getPendingAction(mostRecent.id);
        if (!cancelled) setPendingAction(pending);
      } catch {
        // pending-action is best-effort; messages already loaded
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    refreshNotes();
  }, [refreshNotes]);

  const handleResult = useCallback(
    (result: ChatResult) => {
      setMessages((prev) => [
        ...prev,
        ...(result.transcript ? [{ role: "user" as const, content: result.transcript }] : []),
        { role: "assistant" as const, content: result.reply },
      ]);
      // Only replace the card when this turn produced its own pending action; an
      // unrelated turn (null) leaves the existing one intact.
      setPendingAction((prev) => result.pendingAction ?? prev);
      if (result.sessionId) {
        setActiveSessionId(result.sessionId);
        refreshSessions();
      }
      // A turn may have saved a note via the save_note tool — refresh the list.
      refreshNotes();
    },
    [refreshSessions, refreshNotes]
  );

  const handlePendingActionResolved = useCallback((reply: string) => {
    setMessages((prev) => [...prev, { role: "assistant" as const, content: reply }]);
    setPendingAction(null);
  }, []);

  const handleSelectNote = useCallback(
    async (noteId: string) => {
      if (isBusy) return;
      try {
        setActiveNote(await getNote(noteId));
      } catch {
        // ignore — note selection is best-effort
      }
    },
    [isBusy]
  );

  const handleCloseNote = useCallback(() => setActiveNote(null), []);

  const handleDeleteNote = useCallback(
    async (noteId: string) => {
      try {
        await deleteNote(noteId);
        setActiveNote((current) => (current?.id === noteId ? null : current));
        refreshNotes();
      } catch {
        // ignore — user can retry
      }
    },
    [refreshNotes]
  );

  const handleSelectSession = useCallback(
    async (sessionId: string) => {
      if (isBusy) return;
      setActiveNote(null);
      if (sessionId === activeSessionId) return;
      try {
        const history = await getSessionMessages(sessionId);
        setMessages(history);
        setActiveSessionId(sessionId);
        // The pending action lives server-side per session: drop the card for the
        // session we're leaving, then re-fetch it for the one we're opening so it
        // reappears on return. It's only ever cleared by an explicit confirm/cancel.
        setPendingAction(null);
      } catch {
        // ignore — sidebar selection is best-effort
        return;
      }
      try {
        setPendingAction(await getPendingAction(sessionId));
      } catch {
        // pending-action is best-effort
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
          setPendingAction(null);
          setActiveNote(null);
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
      setPendingAction(null);
      setActiveNote(null);
      refreshSessions();
    } catch {
      // ignore — user can retry
    }
  }, [refreshSessions, isBusy]);

  return (
    <div className="flex h-screen overflow-hidden">
      <SessionSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
        notes={notes}
        activeNoteId={activeNote?.id ?? null}
        onSelectNote={handleSelectNote}
        onSignOut={() => supabase.auth.signOut()}
        canStartNewSession={sessions.find((s) => s.id === activeSessionId)?.isEmpty === false}
        disabled={isBusy}
      />
      <div className="flex flex-1 flex-col items-center gap-5 overflow-hidden px-8 py-6">
        <div className="flex w-full max-w-2xl items-center justify-center">
          <h1 className="text-3xl font-semibold tracking-tight text-zinc-800 dark:text-zinc-100">Sarjy</h1>
        </div>
        {activeNote ? (
          <NoteView note={activeNote} onClose={handleCloseNote} onDelete={handleDeleteNote} />
        ) : (
          <>
            <ChatWindow messages={messages} />
            {pendingAction && activeSessionId && (
              <PendingActionCard
                sessionId={activeSessionId}
                pendingAction={pendingAction}
                onResolved={handlePendingActionResolved}
              />
            )}
            <VoiceInput sessionId={activeSessionId} onResult={handleResult} onBusyChange={setIsBusy} />
          </>
        )}
      </div>
    </div>
  );
}
