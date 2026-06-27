"use client";

import { ConnectionState, Room, RoomEvent } from "livekit-client";
import { useCallback, useEffect, useRef, useState } from "react";
import { getLiveKitToken } from "@/app/lib/api";

export type SessionState =
  | { status: "idle" }
  | { status: "connecting"; room: Room }
  | { status: "connected"; room: Room }
  | { status: "reconnecting"; room: Room }
  | { status: "error"; message: string };

export interface LiveKitSession {
  state: SessionState;
  connect: () => void;
  disconnect: () => void;
}

export function useLiveKitSession(): LiveKitSession {
  const [state, setState] = useState<SessionState>({ status: "idle" });

  const roomRef = useRef<Room | null>(null);
  const connectedRef = useRef(false);
  const intentionalRef = useRef(false);
  const disconnectPromiseRef = useRef<Promise<void> | null>(null);

  const connect = useCallback(async () => {
    if (roomRef.current) return;
    if (disconnectPromiseRef.current) await disconnectPromiseRef.current;
    if (roomRef.current) return;

    intentionalRef.current = false;
    connectedRef.current = false;

    const r = new Room();
    roomRef.current = r;

    r.on(RoomEvent.ConnectionStateChanged, (cs: ConnectionState) => {
      if (roomRef.current !== r) return;
      if (cs === ConnectionState.Connected) {
        connectedRef.current = true;
        setState({ status: "connected", room: r });
      } else if (
        cs === ConnectionState.Reconnecting ||
        cs === ConnectionState.SignalReconnecting
      ) {
        setState({ status: "reconnecting", room: r });
      }
    });

    r.on(RoomEvent.Disconnected, () => {
      const wasConnected = connectedRef.current;
      connectedRef.current = false;
      if (roomRef.current === r) roomRef.current = null;
      if (intentionalRef.current) {
        setState({ status: "idle" });
      } else if (wasConnected) {
        setState({ status: "error", message: "The connection dropped. Reconnect to continue." });
      }
    });

    r.on(RoomEvent.MediaDevicesError, () => {
      if (roomRef.current !== r) return;
      setState({
        status: "error",
        message: "Couldn't access your microphone. Check the browser's mic permission and try again.",
      });
    });

    setState({ status: "connecting", room: r });

    let creds;
    try {
      creds = await getLiveKitToken();
    } catch {
      if (roomRef.current === r) roomRef.current = null;
      setState({
        status: "error",
        message: "Couldn't start a session. Make sure you're signed in and the backend is reachable, then try again.",
      });
      return;
    }

    if (roomRef.current !== r) return;

    try {
      await r.connect(creds.url, creds.token);
      await r.localParticipant.setMicrophoneEnabled(true);
    } catch (e) {
      if (roomRef.current === r) roomRef.current = null;
      const denied = e instanceof Error && e.name === "NotAllowedError";
      setState({
        status: "error",
        message: denied
          ? "Microphone access was blocked. Enable it for this site and try again."
          : "Couldn't connect to the voice session — the agent may be offline. Try again.",
      });
      void r.disconnect();
    }
  }, []);

  const disconnect = useCallback(() => {
    const r = roomRef.current;
    if (!r) return;
    roomRef.current = null;
    intentionalRef.current = true;
    connectedRef.current = false;
    disconnectPromiseRef.current = Promise.resolve(r.disconnect()).finally(() => {
      disconnectPromiseRef.current = null;
    });
    setState({ status: "idle" });
  }, []);

  useEffect(() => {
    return () => {
      intentionalRef.current = true;
      roomRef.current?.disconnect();
      roomRef.current = null;
    };
  }, []);

  return { state, connect, disconnect };
}
