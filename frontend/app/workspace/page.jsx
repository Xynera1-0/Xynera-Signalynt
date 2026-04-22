"use client";

import Link from "next/link";
import { BrainCircuit, LogOut, RefreshCw, Sparkle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import AuthGuard from "../../components/auth/AuthGuard";
import { useAuth } from "../../components/auth/AuthProvider";
import EphemeralRenderer from "../../components/ephemeral/EphemeralRenderer";
import ThemeToggle from "../../components/theme/ThemeToggle";
import { initialMessages } from "../../lib/mockMessages";

function buildMessagesFromSignals(signals, raw) {
  const messages = [];

  if (signals && signals.length > 0) {
    messages.push({
      id: "ws-signal-map",
      role: "agent",
      title: "Live growth signal snapshot",
      uiType: "signal_map",
      ui_payload: {
        territory: "All campaigns",
        signals,
      },
    });
  }

  // Build variant comparison from raw rows that have magnitude data
  const variants = (raw || [])
    .filter((r) => r.affected_variable && r.magnitude != null)
    .slice(0, 6)
    .map((r) => ({
      name: r.affected_variable,
      ctr: Number((parseFloat(r.magnitude) * 100).toFixed(1)),
      cvr: Number((parseFloat(r.confidence || 0) * 100).toFixed(1)),
      sentiment: r.signal_type?.replace(/_/g, " ") || "signal",
      description: r.description,
      campaign_name: r.campaign_name,
    }));

  if (variants.length > 0) {
    messages.push({
      id: "ws-variant-comparison",
      role: "agent",
      title: "Top performing variables",
      uiType: "variant_comparison",
      ui_payload: { variants },
    });
  }

  return messages.length > 0 ? messages : initialMessages;
}

export default function WorkspacePage() {
  const { user, logout, apiGet } = useAuth();
  const [actionFeed, setActionFeed] = useState([]);
  const [messages, setMessages] = useState(initialMessages);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState(null);

  const loadSignals = useCallback(async () => {
    if (!apiGet) return;
    setLoading(true);
    setFetchError(null);
    try {
      const data = await apiGet("/api/v1/campaign/signals/recent?limit=20");
      const built = buildMessagesFromSignals(data?.signals, data?.raw);
      setMessages(built);
    } catch (err) {
      setFetchError(err.message || "Could not load signals");
      setMessages(initialMessages); // fall back to mock
    } finally {
      setLoading(false);
    }
  }, [apiGet]);

  useEffect(() => {
    loadSignals();
  }, [loadSignals]);

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
            <button
              type="button"
              className="btn-ghost"
              onClick={loadSignals}
              disabled={loading}
              title="Refresh signals"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
              {loading ? "Loading…" : "Refresh"}
            </button>
            <Link href="/chat" className="btn-ghost">Open chat</Link>
            <button type="button" className="btn-ghost" onClick={logout}>
              <LogOut className="h-4 w-4" />
              Sign out
            </button>
          </div>
        </header>

        {fetchError && (
          <p className="mb-4 rounded-xl border border-rose-400/25 bg-rose-400/10 px-4 py-2 text-sm text-rose-200">
            Could not fetch live signals — showing demo data. ({fetchError})
          </p>
        )}

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
