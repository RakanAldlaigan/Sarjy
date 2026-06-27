"use client";

import "@livekit/components-styles";
import { useCallback, useEffect, useState } from "react";
import LiveVoice from "@/app/components/LiveVoice";
import NoteView from "@/app/components/NoteView";
import NotesSidebar from "@/app/components/NotesSidebar";
import SignInScreen from "@/app/components/SignInScreen";
import { useAuth } from "@/app/hooks/useAuth";
import { deleteNote, getNote, getNotes, NoteDetail, NoteSummary } from "@/app/lib/api";
import { supabase } from "@/app/lib/supabase";

const NOTES_POLL_MS = 15000;

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

  return <VoiceApp key={session.user.id} />;
}

function VoiceApp() {
  const [notes, setNotes] = useState<NoteSummary[]>([]);
  const [activeNote, setActiveNote] = useState<NoteDetail | null>(null);

  const refreshNotes = useCallback(async () => {
    try {
      setNotes(await getNotes());
    } catch {
    }
  }, []);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const list = await getNotes();
        if (active) setNotes(list);
      } catch {
      }
    };
    load();
    const interval = setInterval(load, NOTES_POLL_MS);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const handleSelectNote = useCallback(async (noteId: string) => {
    try {
      setActiveNote(await getNote(noteId));
    } catch {
    }
  }, []);

  const handleCloseNote = useCallback(() => setActiveNote(null), []);

  const handleDeleteNote = useCallback(
    async (noteId: string) => {
      try {
        await deleteNote(noteId);
        setActiveNote((current) => (current?.id === noteId ? null : current));
        refreshNotes();
      } catch {
      }
    },
    [refreshNotes]
  );

  return (
    <div className="flex h-screen overflow-hidden">
      <NotesSidebar
        notes={notes}
        activeNoteId={activeNote?.id ?? null}
        onSelectNote={handleSelectNote}
        onSignOut={() => supabase.auth.signOut()}
      />
      <main className="relative flex flex-1 flex-col items-center justify-center gap-10 bg-white px-8 dark:bg-zinc-950">
        <div className="flex flex-col items-center gap-1 text-center">
          <h1 className="text-3xl font-semibold tracking-tight text-zinc-800 dark:text-zinc-100">
            Sarjy
          </h1>
          <span className="text-xs font-medium uppercase tracking-wider text-blue-600 dark:text-blue-400">
            Live voice
          </span>
        </div>

        <LiveVoice />

        {activeNote && (
          <div className="absolute inset-0 z-10 flex items-stretch justify-center bg-white/95 p-8 backdrop-blur-sm dark:bg-zinc-950/95">
            <NoteView
              note={activeNote}
              onClose={handleCloseNote}
              onDelete={handleDeleteNote}
              closeLabel="Close"
            />
          </div>
        )}
      </main>
    </div>
  );
}
