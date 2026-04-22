"use client";

import Link from "next/link";
import {
  Download,
  Menu,
  SendHorizonal,
  Settings,
  UserRound,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import AuthGuard from "../../components/auth/AuthGuard";
import { useAuth } from "../../components/auth/AuthProvider";
import EphemeralRenderer from "../../components/ephemeral/EphemeralRenderer";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TOOL_OPTIONS = [
  { id: "research", label: "Research", icon: "travel_explore" },
  {
    id: "generate_content",
    label: "Generate Content",
    icon: "design_services",
  },
  { id: "post_to_channel", label: "Post to Channel", icon: "share" },
  { id: "full_workflow", label: "Full Workflow", icon: "account_tree" },
];
// null = no tool selected — the planner decides from message intent alone

const INITIAL_ASSISTANT_MESSAGE = {
  id: "assistant-welcome",
  role: "assistant",
  content:
    "Hello. I am your campaign assistant. Ask for positioning, channel mix, or next actions.",
  uiType: "text",
  intentDetected: null,
  signalIds: [],
  metadata: {},
};

function formatChatTitle(input) {
  const trimmed = input.trim();
  if (!trimmed) return "Untitled conversation";
  const words = trimmed.split(/\s+/).slice(0, 5).join(" ");
  return words.length < trimmed.length ? `${words}...` : words;
}

function createConversation() {
  return {
    id: crypto.randomUUID(),
    title: "New conversation",
    tool: null,
    updatedAt: Date.now(),
    messages: [{ ...INITIAL_ASSISTANT_MESSAGE, id: crypto.randomUUID() }],
  };
}

// ---------------------------------------------------------------------------
// FlyerPanel — right-side panel shown when a flyer thumbnail is clicked
// ---------------------------------------------------------------------------

function FlyerPanel({ data, onClose }) {
  const { flyerImageUrl, content = {}, critique = {} } = data;
  const headlines = content.headlines || [];
  const body = content.body || "";
  const cta = content.cta || "";
  const finalOutput = critique.final_output || "";
  const variations = content.variations || {};

  return (
    <aside className="flex w-[340px] shrink-0 flex-col gap-4 overflow-y-auto border-l border-slate-800 bg-slate-950 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-lg text-teal-400">
            design_services
          </span>
          <p className="text-sm font-semibold text-[#dae2fd]">
            Generated Flyer
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1 text-slate-400 transition hover:bg-slate-800 hover:text-[#dae2fd]"
          aria-label="Close panel"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Image with text overlay */}
      <div className="group relative select-none overflow-hidden rounded-xl border border-teal-500/10">
        {flyerImageUrl ? (
          <img
            src={flyerImageUrl}
            alt={headlines[0] || "Flyer"}
            className="aspect-[3/4] w-full object-cover opacity-90 transition-transform duration-500 group-hover:scale-105"
          />
        ) : (
          <div className="flex aspect-[3/4] items-center justify-center bg-[#131b2e]">
            <p className="text-xs text-slate-500">No image generated</p>
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-slate-900/60 to-transparent" />
        <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-5">
          <div>
            {headlines[0] && (
              <p
                className="text-xl font-black leading-tight"
                style={{
                  color: "#fff",
                  textShadow: "0 2px 12px rgba(0,0,0,0.95)",
                }}
              >
                {headlines[0]}
              </p>
            )}
          </div>
          <div className="space-y-2">
            {body && (
              <p
                className="text-sm leading-snug"
                style={{
                  color: "rgba(255,255,255,0.92)",
                  textShadow: "0 1px 6px rgba(0,0,0,0.9)",
                }}
              >
                {body}
              </p>
            )}
            {cta && (
              <div
                className="inline-block rounded px-3 py-1.5 text-sm font-bold"
                style={{
                  background: "rgba(54,209,193,0.9)",
                  color: "#003732",
                  boxShadow: "0 2px 8px rgba(0,0,0,0.4)",
                }}
              >
                {cta}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        {flyerImageUrl && (
          <a
            href={flyerImageUrl}
            download="flyer.jpg"
            target="_blank"
            rel="noreferrer"
            className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-slate-700 bg-slate-900 py-2 text-xs font-semibold text-slate-300 transition hover:bg-slate-800"
          >
            <Download className="h-3.5 w-3.5" />
            Download
          </a>
        )}
        <button className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-slate-700 bg-slate-900 py-2 text-xs font-semibold text-slate-300 transition hover:bg-slate-800">
          <span className="material-symbols-outlined text-sm">share</span>
          Share
        </button>
      </div>

      {/* Badge */}
      <div className="flex items-center justify-between rounded-lg bg-[#131b2e] px-3 py-2">
        <span className="text-[11px] text-slate-400">
          Ready for distribution (A4 / 300DPI)
        </span>
        <span className="rounded border border-teal-400/20 bg-teal-400/10 px-2 py-0.5 text-[10px] font-bold text-teal-400">
          HD RENDER
        </span>
      </div>

      {headlines.length > 1 && (
        <div className="rounded-xl border border-slate-800 bg-[#131b2e] p-3">
          <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-teal-400">
            Headlines
          </p>
          <ul className="space-y-1">
            {headlines.map((h, i) => (
              <li key={i} className="text-sm text-[#dae2fd]">
                {h}
              </li>
            ))}
          </ul>
        </div>
      )}

      {Object.keys(variations).length > 0 && (
        <div className="rounded-xl border border-slate-800 bg-[#131b2e] p-3">
          <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-teal-400">
            Variations
          </p>
          {Object.entries(variations).map(([key, val]) => (
            <div key={key} className="mb-2">
              <p className="text-[10px] font-semibold capitalize text-slate-500">
                {key.replace(/_/g, " ")}
              </p>
              <p className="text-xs text-[#dae2fd]">{val}</p>
            </div>
          ))}
        </div>
      )}

      {finalOutput && (
        <div className="rounded-xl border border-teal-900/40 bg-teal-950/20 p-3">
          <p className="mb-1 text-[10px] font-bold uppercase tracking-widest text-teal-400">
            Final Copy
          </p>
          <p className="whitespace-pre-wrap text-xs text-slate-300">
            {finalOutput}
          </p>
        </div>
      )}
    </aside>
  );
}

// ---------------------------------------------------------------------------
// ChatPage
// ---------------------------------------------------------------------------

export default function ChatPage() {
  const { user, accessToken, apiGet, apiPost } = useAuth();
  const [input, setInput] = useState("");
  const [conversations, setConversations] = useState([createConversation()]);
  const [activeConversationId, setActiveConversationId] = useState(
    conversations[0].id,
  );
  const [selectedTool, setSelectedTool] = useState(null);
  const [isSending, setIsSending] = useState(false);
  const [sendError, setSendError] = useState(null);
  const [flyerPanel, setFlyerPanel] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const messagesEndRef = useRef(null);

  const activeConversation = useMemo(
    () =>
      conversations.find((c) => c.id === activeConversationId) ||
      conversations[0],
    [activeConversationId, conversations],
  );

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeConversation?.messages?.length]);

  // Load conversation history from backend on mount
  useEffect(() => {
    let cancelled = false;
    async function loadHistory() {
      if (!accessToken) return;
      try {
        const listPayload = await apiGet("/chat/conversations");
        const remoteConversations = listPayload.conversations || [];
        if (!remoteConversations.length) return;

        const withMessages = await Promise.all(
          remoteConversations.map(async (conv) => {
            const payload = await apiGet(
              `/chat/conversations/${conv.id}/messages`,
            );
            const messages = (payload.messages || []).map((item) => ({
              id: item.id,
              role: item.role,
              content: item.content,
              tool: item.tool,
              uiType: item.ui_type,
              intentDetected: item.intent_detected,
              signalIds: item.signal_ids || [],
              metadata: item.metadata || {},
              flyerImageUrl: item.metadata?.flyer_image_source_url || null,
            }));
            return {
              id: conv.id,
              title: conv.title,
              tool: conv.tool || null,
              updatedAt: conv.updated_at
                ? new Date(conv.updated_at).getTime()
                : Date.now(),
              messages: messages.length
                ? messages
                : [{ ...INITIAL_ASSISTANT_MESSAGE, id: crypto.randomUUID() }],
            };
          }),
        );

        if (!cancelled) {
          const ordered = withMessages.sort(
            (a, b) => b.updatedAt - a.updatedAt,
          );
          setConversations(ordered);
          setActiveConversationId(ordered[0].id);
          // Don't restore tool on load — user picks it intentionally
          setSelectedTool(null);
        }
      } catch {
        // Keep in-memory fallback
      }
    }
    loadHistory();
    return () => {
      cancelled = true;
    };
  }, [accessToken, apiGet]);

  function createNewConversation() {
    const next = createConversation();
    setConversations((prev) => [next, ...prev]);
    setActiveConversationId(next.id);
    setSelectedTool(null);
    setInput("");
  }

  function openConversation(id) {
    const found = conversations.find((c) => c.id === id);
    if (!found) return;
    setActiveConversationId(id);
    setSelectedTool(found.tool || null);
  }

  async function sendMessage(e) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isSending || !activeConversation) return;

    const conversationId = activeConversation.id;
    const conversationTitle =
      activeConversation.messages.length <= 1
        ? formatChatTitle(trimmed)
        : activeConversation.title;

    const optimisticUserMsg = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
      uiType: "prompt",
      intentDetected: selectedTool,
      signalIds: [],
      metadata: {},
    };
    const optimisticAssistantMsg = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "Running agent...",
      uiType: "text",
      intentDetected: selectedTool,
      signalIds: [],
      metadata: {},
    };

    setIsSending(true);
    setSendError(null);
    setConversations((prev) =>
      prev
        .map((c) =>
          c.id !== conversationId
            ? c
            : {
                ...c,
                title: conversationTitle,
                tool: selectedTool,
                updatedAt: Date.now(),
                messages: [
                  ...c.messages,
                  optimisticUserMsg,
                  optimisticAssistantMsg,
                ],
              },
        )
        .sort((a, b) => b.updatedAt - a.updatedAt),
    );

    try {
      if (accessToken) {
        // Single endpoint: upserts conversation + runs full supervisor graph + persists both messages
        const response = await apiPost(
          `/chat/conversations/${conversationId}/send`,
          {
            message: trimmed,
            tool: selectedTool || "",
            title: conversationTitle,
            workspace_id: user?.workspace_id || "",
          },
        );

        const assistantMsg = response.assistant_message;
        const flyerImageUrl = assistantMsg?.ui_payload?.flyerImageUrl || null;

        setConversations((prev) =>
          prev
            .map((conv) => {
              if (conv.id !== conversationId) return conv;
              const msgs = [...conv.messages];
              msgs[msgs.length - 2] = {
                ...msgs[msgs.length - 2],
                id: response.user_message_id,
              };
              msgs[msgs.length - 1] = {
                id: assistantMsg.id,
                role: "assistant",
                content: assistantMsg.content,
                uiType: assistantMsg.ui_type,
                intentDetected: assistantMsg.intent_detected,
                signalIds: assistantMsg.signal_ids || [],
                metadata: assistantMsg.ui_payload || {},
                flyerImageUrl,
                result: assistantMsg.ui_payload?.result || null,
              };
              return {
                ...conv,
                title: conversationTitle,
                tool: selectedTool,
                updatedAt: Date.now(),
                messages: msgs,
              };
            })
            .sort((a, b) => b.updatedAt - a.updatedAt),
        );
      } else {
        // Offline fallback
        setConversations((prev) =>
          prev
            .map((conv) => {
              if (conv.id !== conversationId) return conv;
              const msgs = [...conv.messages];
              msgs[msgs.length - 1] = {
                ...msgs[msgs.length - 1],
                content: "I am offline. Start the backend to use the AI.",
                uiType: "text",
              };
              return {
                ...conv,
                title: conversationTitle,
                updatedAt: Date.now(),
                messages: msgs,
              };
            })
            .sort((a, b) => b.updatedAt - a.updatedAt),
        );
      }

      setInput("");
    } catch (err) {
      const errMsg =
        err instanceof Error ? err.message : "Agent request failed.";
      setSendError(errMsg);
      setConversations((prev) =>
        prev
          .map((c) => {
            if (c.id !== conversationId) return c;
            const msgs = [...c.messages];
            msgs[msgs.length - 1] = {
              ...msgs[msgs.length - 1],
              content: `Error: ${errMsg}`,
            };
            return { ...c, updatedAt: Date.now(), messages: msgs };
          })
          .sort((a, b) => b.updatedAt - a.updatedAt),
      );
    } finally {
      setIsSending(false);
    }
  }

  return (
    <AuthGuard>
      {/* Full-viewport shell */}
      <div className="flex h-screen overflow-hidden bg-[#0b1326] font-inter text-[#dae2fd]">
        {/* Mobile sidebar backdrop */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-40 bg-slate-950/60 backdrop-blur-sm lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Left sidebar */}
        <aside
          className={`fixed inset-y-0 left-0 z-50 flex w-64 shrink-0 flex-col border-r border-slate-800 bg-slate-950 transition-transform duration-300 lg:static lg:translate-x-0 ${
            sidebarOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <div className="flex-1 overflow-y-auto px-4 pt-6">
            <div className="mb-6 flex items-center gap-3 px-2">
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

            <button
              type="button"
              onClick={() => {
                createNewConversation();
                setSidebarOpen(false);
              }}
              className="mb-6 flex w-full items-center justify-center gap-2 rounded bg-[#36d1c1] py-3 text-sm font-bold text-[#003732] transition hover:brightness-110 active:scale-95"
            >
              <span className="material-symbols-outlined text-lg">add</span>
              New Chat
            </button>

            <nav className="space-y-1">
              <p className="mb-2 px-2 text-[11px] font-bold uppercase tracking-widest text-slate-500">
                Recent Chats
              </p>
              {conversations.map((conv) => {
                const isActive = conv.id === activeConversation?.id;
                return (
                  <button
                    key={conv.id}
                    type="button"
                    onClick={() => {
                      openConversation(conv.id);
                      setSidebarOpen(false);
                    }}
                    className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-all duration-200 ${
                      isActive
                        ? "border-r-2 border-teal-400 bg-teal-400/5 text-teal-400"
                        : "text-slate-500 hover:bg-slate-900 hover:text-slate-200"
                    }`}
                  >
                    <span className="material-symbols-outlined text-[20px]">
                      chat
                    </span>
                    <span className="truncate">{conv.title}</span>
                  </button>
                );
              })}
            </nav>
          </div>

          <div className="mt-auto border-t border-slate-900 px-4 pb-4 pt-6">
            <Link
              href="/workspace"
              className="mb-1 flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-500 transition-all hover:bg-slate-900 hover:text-slate-200"
            >
              <span className="material-symbols-outlined text-[20px]">
                dashboard
              </span>
              Workspace
            </Link>
            <a
              href="#"
              className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-500 transition-all hover:bg-slate-900 hover:text-slate-200"
            >
              <span className="material-symbols-outlined text-[20px]">
                contact_support
              </span>
              Support
            </a>
          </div>
        </aside>

        {/* Main column */}
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          {/* Top navbar */}
          <header className="z-30 flex h-16 shrink-0 items-center justify-between border-b border-slate-800 bg-slate-900/80 px-4 backdrop-blur-md sm:px-6">
            <div className="flex items-center gap-4">
              <button
                type="button"
                onClick={() => setSidebarOpen((v) => !v)}
                className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-800/50 active:scale-95 lg:hidden"
                aria-label="Open sidebar"
              >
                <Menu className="h-5 w-5" />
              </button>
              <span className="font-manrope text-xl font-bold tracking-tighter text-teal-400">
                Xynera
              </span>
              <div className="hidden items-center rounded-lg border border-slate-700/50 bg-slate-800/50 px-3 py-1.5 md:flex">
                <span className="material-symbols-outlined mr-2 text-[20px] text-slate-400">
                  search
                </span>
                <input
                  className="w-56 border-none bg-transparent text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-0"
                  placeholder="Search workspace..."
                  type="text"
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-800/50 active:scale-95">
                <Settings className="h-5 w-5" />
              </button>
              <div className="ml-1 flex h-8 w-8 items-center justify-center rounded-full border border-slate-700 bg-slate-800">
                <UserRound className="h-4 w-4 text-teal-400" />
              </div>
            </div>
          </header>

          {/* Body: messages + optional flyer panel */}
          <div className="flex flex-1 overflow-hidden">
            {/* Messages column */}
            <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
              {/* Scrollable message history */}
              <div className="flex-1 overflow-y-auto px-4 py-8 sm:px-6">
                <div className="mx-auto max-w-[800px] space-y-8">
                  {activeConversation?.messages.map((message) => {
                    const isUser = message.role === "user";
                    const hasRichUI =
                      !isUser &&
                      message.uiType &&
                      message.uiType !== "text" &&
                      message.uiType !== "prompt";

                    if (isUser) {
                      return (
                        <div
                          key={message.id}
                          className="flex flex-col items-end space-y-2"
                        >
                          <div className="max-w-[80%] rounded-xl rounded-tr-none border border-teal-400/30 bg-[#222a3d] p-4 shadow-lg">
                            <p className="break-words text-sm text-[#dae2fd]">
                              {message.content}
                            </p>
                          </div>
                          <span className="mr-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                            {message.intentDetected
                              ? TOOL_OPTIONS.find(
                                  (t) => t.id === message.intentDetected,
                                )?.label || message.intentDetected
                              : "you"}
                          </span>
                        </div>
                      );
                    }

                    return (
                      <div
                        key={message.id}
                        className="flex flex-col items-start space-y-3"
                      >
                        <div className="flex w-full items-start gap-4">
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-teal-500/20 bg-teal-500/10">
                            <span className="material-symbols-outlined text-lg text-teal-400">
                              auto_awesome
                            </span>
                          </div>
                          <div className="min-w-0 flex-1 space-y-4">
                            {hasRichUI ? (
                              <EphemeralRenderer
                                message={{
                                  ...message,
                                  ui_type: message.uiType,
                                  ui_payload: {
                                    ...(message.ui_payload ||
                                      message.metadata ||
                                      {}),
                                    flyerImageUrl:
                                      message.flyerImageUrl || null,
                                    result: message.result || null,
                                  },
                                }}
                                onAction={(action) => setInput(action)}
                                onExpand={(flyerData) =>
                                  setFlyerPanel(flyerData)
                                }
                              />
                            ) : (
                              <div className="max-w-[90%] rounded-xl rounded-tl-none border border-slate-800 bg-[#131b2e] p-4 shadow-sm">
                                {typeof message.content === "string" ? (
                                  <p className="break-words text-sm leading-relaxed text-[#dae2fd]">
                                    {message.content}
                                  </p>
                                ) : (
                                  <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-[#dae2fd]">
                                    {JSON.stringify(message.content, null, 2)}
                                  </pre>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                        <span className="ml-12 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                          AI ASSISTANT
                        </span>
                      </div>
                    );
                  })}

                  {sendError && (
                    <div className="rounded-xl border border-rose-400/25 bg-rose-400/10 px-4 py-3 text-sm text-rose-200">
                      {sendError}
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>
              </div>

              {/* Fixed bottom input bar */}
              <div className="shrink-0 border-t border-slate-800/50 bg-slate-950/80 px-4 py-4 backdrop-blur-xl sm:px-6">
                <div className="mx-auto max-w-[800px]">
                  <form onSubmit={sendMessage}>
                    {/* Input row */}
                    <div className="flex items-center gap-2 rounded-xl border border-slate-700/50 bg-[#2d3449]/50 px-3 py-1.5 shadow-inner transition-all focus-within:border-teal-400/50">
                      <button
                        type="button"
                        onClick={createNewConversation}
                        className="shrink-0 p-1.5 text-slate-400 transition hover:text-teal-400"
                        title="New chat"
                      >
                        <span className="material-symbols-outlined text-[22px]">
                          add_circle
                        </span>
                      </button>

                      {/* Active mode chip — shown inline only when a tool is selected */}
                      {selectedTool &&
                        (() => {
                          const active = TOOL_OPTIONS.find(
                            (o) => o.id === selectedTool,
                          );
                          return active ? (
                            <button
                              type="button"
                              onClick={() => setSelectedTool(null)}
                              className="flex shrink-0 items-center gap-1.5 rounded-full border border-teal-400/40 bg-teal-400/10 px-2.5 py-1 text-[11px] font-semibold text-teal-400 transition hover:bg-teal-400/20"
                              title="Clear mode"
                            >
                              <span className="material-symbols-outlined text-[14px]">
                                {active.icon}
                              </span>
                              {active.label}
                              <X className="h-3 w-3" />
                            </button>
                          ) : null;
                        })()}

                      <input
                        className="min-w-0 flex-1 border-none bg-transparent py-3 text-sm text-[#dae2fd] placeholder-slate-500 focus:outline-none focus:ring-0"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder={
                          selectedTool
                            ? "What do you need?"
                            : "Ask anything, or pick a mode below..."
                        }
                        disabled={isSending}
                      />

                      <button
                        type="submit"
                        disabled={isSending || !input.trim()}
                        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#36d1c1] text-[#003732] shadow-lg shadow-teal-500/10 transition hover:brightness-110 active:scale-90 disabled:opacity-40"
                      >
                        <SendHorizonal className="h-4 w-4" />
                      </button>
                    </div>

                    {/* Mode chips — click to select, click active chip to deselect */}
                    <div className="mt-3 flex flex-wrap justify-center gap-2">
                      {TOOL_OPTIONS.map((t) => {
                        const isActive = selectedTool === t.id;
                        return (
                          <button
                            key={t.id}
                            type="button"
                            onClick={() =>
                              setSelectedTool(isActive ? null : t.id)
                            }
                            className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-medium transition-all ${
                              isActive
                                ? "border-teal-400/50 bg-teal-400/10 text-teal-400 shadow-sm shadow-teal-400/10"
                                : "border-slate-800 text-slate-500 hover:border-slate-600 hover:text-slate-300"
                            }`}
                          >
                            <span className="material-symbols-outlined text-[13px]">
                              {t.icon}
                            </span>
                            {t.label}
                          </button>
                        );
                      })}
                    </div>

                    <div className="h-2" />
                  </form>
                </div>
              </div>
            </div>

            {/* Right flyer panel (desktop) */}
            {flyerPanel && (
              <FlyerPanel
                data={flyerPanel}
                onClose={() => setFlyerPanel(null)}
              />
            )}
          </div>
        </div>
      </div>

      {/* Mobile flyer panel overlay */}
      {flyerPanel && (
        <div className="fixed inset-0 z-50 flex items-end justify-center lg:hidden">
          <div
            className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm"
            onClick={() => setFlyerPanel(null)}
          />
          <div className="relative z-10 max-h-[85vh] w-full overflow-y-auto rounded-t-2xl border-t border-slate-800 bg-slate-950">
            <FlyerPanel data={flyerPanel} onClose={() => setFlyerPanel(null)} />
          </div>
        </div>
      )}
    </AuthGuard>
  );
}
