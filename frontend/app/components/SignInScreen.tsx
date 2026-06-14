"use client";

import { supabase } from "@/app/lib/supabase";

export default function SignInScreen() {
  const handleSignIn = () => {
    supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: window.location.origin,
        queryParams: { prompt: "select_account" },
      },
    });
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-white px-8 dark:bg-zinc-950">
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-800 dark:text-zinc-100">Sarjy</h1>
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Sign in to capture notes, tasks, and reminders by voice.
        </p>
      </div>

      <button
        onClick={handleSignIn}
        className="flex items-center gap-3 rounded-xl bg-blue-600 px-5 py-3 text-sm font-medium text-white shadow-sm transition-colors duration-150 hover:bg-blue-500"
      >
        <svg className="h-5 w-5" viewBox="0 0 24 24" aria-hidden="true">
          <path
            fill="#FFFFFF"
            d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
          />
          <path
            fill="#FFFFFF"
            d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.99.69-2.26 1.1-3.71 1.1-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
          />
          <path
            fill="#FFFFFF"
            d="M5.84 14.14c-.22-.69-.35-1.43-.35-2.14s.13-1.45.35-2.14V7.02H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.98l2.85-2.22.81-.62z"
          />
          <path
            fill="#FFFFFF"
            d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.02l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
          />
        </svg>
        Sign in with Google
      </button>
    </div>
  );
}
