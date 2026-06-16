"use client";

import { useEffect, useState } from "react";
import { disconnectCalendar, getCalendarConnectUrl, getCalendarStatus } from "@/app/lib/api";

function readCalendarNotice(): string | null {
  if (typeof window === "undefined") return null;

  const params = new URLSearchParams(window.location.search);
  const calendarParam = params.get("calendar");
  if (!calendarParam) return null;

  return calendarParam === "connected"
    ? "Google Calendar connected."
    : "Couldn't connect Google Calendar. Please try again.";
}

export default function CalendarConnect() {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [notice] = useState<string | null>(readCalendarNotice);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!notice) return;

    const params = new URLSearchParams(window.location.search);
    params.delete("calendar");
    const rest = params.toString();
    window.history.replaceState({}, "", rest ? `${window.location.pathname}?${rest}` : window.location.pathname);
  }, [notice]);

  useEffect(() => {
    getCalendarStatus()
      .then(setConnected)
      .catch(() => setConnected(false));
  }, []);

  const handleConnect = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const url = await getCalendarConnectUrl();
      window.location.href = url;
    } catch {
      setBusy(false);
    }
  };

  const handleDisconnect = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await disconnectCalendar();
      setConnected(false);
    } catch {
      // ignore — user can retry
    } finally {
      setBusy(false);
    }
  };

  if (connected === null) {
    return null;
  }

  return (
    <div className="flex flex-col gap-1">
      {notice && <span className="px-1 text-xs text-zinc-400 dark:text-zinc-500">{notice}</span>}
      {connected ? (
        <button
          onClick={handleDisconnect}
          disabled={busy}
          className="rounded-xl bg-red-500/10 px-3 py-2 text-sm font-medium text-red-600 transition-colors duration-150 hover:bg-red-500/20 disabled:opacity-50 dark:text-red-400"
        >
          Calendar connected · Disconnect
        </button>
      ) : (
        <button
          onClick={handleConnect}
          disabled={busy}
          className="rounded-xl bg-emerald-500/10 px-3 py-2 text-sm font-medium text-emerald-600 transition-colors duration-150 hover:bg-emerald-500/20 disabled:opacity-50 dark:text-emerald-400"
        >
          Connect Google Calendar
        </button>
      )}
    </div>
  );
}
