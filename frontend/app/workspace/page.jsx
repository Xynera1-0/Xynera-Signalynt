"use client";

import Link from "next/link";
import { BrainCircuit, LogOut, Sparkle } from "lucide-react";
import { useMemo, useState } from "react";
import AuthGuard from "../../components/auth/AuthGuard";
import { useAuth } from "../../components/auth/AuthProvider";
import EphemeralRenderer from "../../components/ephemeral/EphemeralRenderer";
import ThemeToggle from "../../components/theme/ThemeToggle";
import { initialMessages } from "../../lib/mockMessages";

export default function WorkspacePage() {
  const { user, logout } = useAuth();
  const [actionFeed, setActionFeed] = useState([]);

  const messages = useMemo(() => initialMessages, []);

  function handleAction(actionText) {
    setActionFeed((prev) => [
      {
        id: crypto.randomUUID(),
        text: actionText,
        ts: new Date().toLocaleTimeString(),
      },
      ...prev,
    ]);
  }

  return (
    <AuthGuard>
      <main className="mx-auto w-full max-w-7xl px-4 py-6 md:py-10">
        <header className="glass-panel mb-6 flex flex-wrap items-center justify-between gap-4 rounded-2xl px-5 py-4">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-brand-300">Signal to Action</p>
            <h1 className="text-main mt-1 flex items-center gap-2 text-xl font-bold md:text-2xl">
              <BrainCircuit className="h-6 w-6 text-brand-300" />
              Growth Campaign Workspace
            </h1>
            <p className="text-soft mt-1 text-sm">Welcome {user?.name || "operator"}. Your intelligence loop is live.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <ThemeToggle />
            <Link href="/chat" className="btn-ghost">Open chat</Link>
            <button type="button" className="btn-ghost" onClick={logout}>
              <LogOut className="h-4 w-4" />
              Sign out
            </button>
          </div>
        </header>

        <section className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
          <div className="space-y-4">
            {messages.map((message) => (
              <article key={message.id}>
                <p className="text-muted mb-2 text-xs uppercase tracking-[0.15em]">{message.title}</p>
                <EphemeralRenderer message={message} onAction={handleAction} />
              </article>
            ))}
          </div>

          <aside className="glass-panel rounded-2xl p-5">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-brand-200">
              <Sparkle className="h-4 w-4" />
              Action feed
            </h2>
            <p className="text-muted mt-1 text-xs">Click decisions appear here to drive the next agent cycle.</p>

            <div className="mt-4 space-y-2">
              {actionFeed.length === 0 && (
                <div className="text-muted rounded-xl border border-dashed border-slate-500/40 bg-black/5 p-3 text-xs">
                  No actions yet. Pick a variant or channel to continue the loop.
                </div>
              )}
              {actionFeed.map((item) => (
                <div key={item.id} className="rounded-xl border border-slate-500/40 bg-black/10 p-3">
                  <p className="text-main text-sm">{item.text}</p>
                  <p className="text-muted mt-1 text-xs">{item.ts}</p>
                </div>
              ))}
            </div>
          </aside>
        </section>
      </main>
    </AuthGuard>
  );
}
