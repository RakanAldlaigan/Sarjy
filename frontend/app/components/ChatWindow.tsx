"use client";

import { useEffect, useRef } from "react";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface ChatWindowProps {
  messages: ChatMessage[];
}

export default function ChatWindow({ messages }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex h-full min-h-0 w-full max-w-2xl flex-1 flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-zinc-200 px-6 text-center dark:border-zinc-800">
        <p className="text-base font-medium text-zinc-600 dark:text-zinc-300">
          Ready when you are
        </p>
        <p className="max-w-xs text-sm text-zinc-400 dark:text-zinc-500">
          Press the button below and start talking
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 w-full max-w-2xl flex-1 flex-col gap-3 overflow-y-auto rounded-2xl border border-zinc-200 bg-zinc-50/50 p-5 dark:border-zinc-800 dark:bg-zinc-900/40">
      {messages.map((message, index) => (
        <div
          key={index}
          className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed shadow-sm ${
            message.role === "user"
              ? "self-end rounded-br-md bg-blue-600 text-white"
              : "self-start rounded-bl-md bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
          }`}
        >
          {message.content}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
