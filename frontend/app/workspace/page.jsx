"use client";

import Link from "next/link";
import { Settings } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import AuthGuard from "../../components/auth/AuthGuard";
import { useAuth } from "../../components/auth/AuthProvider";

// ────────────────────────────────────────────────────────────────────────────
// Quick-launch cards — link to chat page (no fake data)
// ────────────────────────────────────────────────────────────────────────────
const QUICK_ACTIONS = [
  {
    label: "Generate Flyer",
    icon: "design_services",
    desc: "AI-designed marketing flyer with image",
  },
  {
    label: "Write Email",
    icon: "mail",
    desc: "Campaign email copy with subject lines",
  },
  {
    label: "Social Post",
    icon: "share",
    desc: "Platform-ready social content",
  },
  {
    label: "Write Blog",
    icon: "article",
    desc: "Long-form brand blog content",
  },
  {
    label: "Research Market",
    icon: "travel_explore",
    desc: "Trends, competitors & audience signals",
  },
  {
    label: "Full Workflow",
    icon: "account_tree",
    desc: "Research → Content → Distribution",
  },
];

const TOOL_ICONS = {
  research: "travel_explore",
  generate_content: "design_services",
  post_to_channel: "share",
  full_workflow: "account_tree",
};

function formatRelativeTime(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// ────────────────────────────────────────────────────────────────────────────
// WorkspacePage
// ────────────────────────────────────────────────────────────────────────────
export default function WorkspacePage() {
  const { user, logout, apiGet } = useAuth();
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(false);

  const loadConversations = useCallback(async () => {
    if (!apiGet) return;
    setLoading(true);
    try {
      const data = await apiGet("/chat/conversations");
      setConversations(
        Array.isArray(data?.conversations)
          ? data.conversations.slice(0, 10)
          : [],
      );
    } catch {
      setConversations([]);
    } finally {
      setLoading(false);
    }
  }, [apiGet]);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const initials = (user?.name || user?.email || "U")[0].toUpperCase();

  return (
    <AuthGuard>
      {/* Full-viewport shell — matches chat page */}
      <div className="flex h-screen overflow-hidden bg-[#0b1326] font-inter text-[#dae2fd]">
        {/* ── Left sidebar ── */}
        <aside className="flex w-64 shrink-0 flex-col border-r border-slate-800 bg-slate-950">
          <div className="flex-1 overflow-y-auto px-4 pt-6">
            {/* Brand */}
            <div className="mb-8 flex items-center gap-3 px-2">
              <div className="flex h-8 w-8 items-center justify-center rounded border border-teal-400/30 bg-teal-400/20">
                <span className="material-symbols-outlined text-lg text-teal-400">
                  auto_awesome
                </span>
              </div>
              <div>
                <p className="text-sm font-bold text-[#dae2fd]">Xynera Pro</p>
                <p className="text-[10px] uppercase tracking-widest text-slate-500">
                  AI High-Performance
                </p>
              </div>
            </div>

            {/* Nav */}
            <nav className="space-y-1">
              <Link
                href="/chat"
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-400 transition hover:bg-slate-800 hover:text-[#dae2fd]"
              >
                <span className="material-symbols-outlined text-[20px]">
                  chat
                </span>
                Chat
              </Link>
              <div className="flex w-full items-center gap-3 rounded-lg border-r-2 border-teal-400 bg-teal-400/10 px-3 py-2.5 text-sm text-teal-400">
                <span className="material-symbols-outlined text-[20px]">
                  dashboard
                </span>
                Workspace
              </div>
            </nav>
          </div>

          {/* Sidebar footer */}
          <div className="border-t border-slate-800 px-4 py-4">
            <button
              type="button"
              onClick={logout}
              className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-400 transition hover:bg-slate-800 hover:text-rose-400"
            >
              <span className="material-symbols-outlined text-[20px]">
                logout
              </span>
              Sign out
            </button>
          </div>
        </aside>

        {/* ── Main column ── */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Top navbar */}
          <header className="flex h-16 shrink-0 items-center justify-between border-b border-slate-800 bg-slate-900/80 px-6 backdrop-blur-md">
            <div>
              <h1 className="font-manrope text-base font-bold text-[#5deedd]">
                Workspace
              </h1>
              <p className="text-[11px] text-slate-500">
                Welcome back,{" "}
                {user?.name || user?.email?.split("@")[0] || "operator"}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={loadConversations}
                disabled={loading}
                className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-800 disabled:opacity-40"
                title="Refresh"
              >
                <span
                  className={`material-symbols-outlined text-[20px] ${loading ? "animate-spin" : ""}`}
                >
                  {loading ? "progress_activity" : "refresh"}
                </span>
              </button>
              <button className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-800">
                <Settings className="h-4 w-4" />
              </button>
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-teal-400/20 text-xs font-bold text-teal-400">
                {initials}
              </div>
            </div>
          </header>

          {/* Scrollable body */}
          <div className="flex-1 overflow-y-auto px-6 py-8">
            <div className="mx-auto max-w-4xl space-y-10">
              {/* Quick Actions */}
              <section>
                <h2 className="mb-4 text-[11px] font-bold uppercase tracking-widest text-slate-500">
                  Quick Actions
                </h2>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {QUICK_ACTIONS.map((action) => (
                    <Link
                      key={action.label}
                      href="/chat"
                      className="group flex flex-col gap-3 rounded-xl border border-slate-800 bg-[#131b2e] p-4 transition hover:border-teal-400/30 hover:bg-[#1a243d]"
                    >
                      <span className="material-symbols-outlined text-[28px] text-slate-600 transition group-hover:text-teal-400">
                        {action.icon}
                      </span>
                      <div>
                        <p className="text-sm font-semibold text-[#dae2fd]">
                          {action.label}
                        </p>
                        <p className="mt-0.5 text-[11px] leading-relaxed text-slate-500">
                          {action.desc}
                        </p>
                      </div>
                    </Link>
                  ))}
                </div>
              </section>

              {/* Recent Conversations */}
              <section>
                <h2 className="mb-4 text-[11px] font-bold uppercase tracking-widest text-slate-500">
                  Recent Conversations
                </h2>

                {loading ? (
                  <div className="flex items-center gap-3 rounded-xl border border-slate-800 bg-[#131b2e] px-5 py-4 text-sm text-slate-500">
                    <span className="material-symbols-outlined animate-spin text-[18px] text-teal-400">
                      progress_activity
                    </span>
                    Loading…
                  </div>
                ) : conversations.length === 0 ? (
                  <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-800 bg-[#131b2e] py-14 text-center">
                    <span className="material-symbols-outlined text-[44px] text-slate-700">
                      chat_bubble
                    </span>
                    <p className="mt-3 text-sm text-slate-500">
                      No conversations yet.
                    </p>
                    <Link
                      href="/chat"
                      className="mt-4 rounded-lg bg-[#36d1c1] px-4 py-2 text-xs font-bold text-[#003732] transition hover:brightness-110"
                    >
                      Start your first chat
                    </Link>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {conversations.map((conv) => (
                      <Link
                        key={conv.id}
                        href="/chat"
                        className="flex items-center gap-4 rounded-xl border border-slate-800 bg-[#131b2e] px-5 py-3.5 transition hover:border-teal-400/20 hover:bg-[#1a243d]"
                      >
                        <span className="material-symbols-outlined text-[20px] text-slate-600">
                          {TOOL_ICONS[conv.tool] || "chat"}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-[#dae2fd]">
                            {conv.title || "Untitled conversation"}
                          </p>
                          <p className="mt-0.5 text-[11px] capitalize text-slate-500">
                            {conv.tool?.replace(/_/g, " ") || "full workflow"}
                            {conv.updated_at && (
                              <span className="ml-2 text-slate-600">
                                · {formatRelativeTime(conv.updated_at)}
                              </span>
                            )}
                          </p>
                        </div>
                        <span className="material-symbols-outlined text-[16px] text-slate-700">
                          chevron_right
                        </span>
                      </Link>
                    ))}
                  </div>
                )}
              </section>
            </div>
          </div>
        </div>
      </div>
    </AuthGuard>
  );
}
