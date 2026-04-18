"use client";

import Link from "next/link";
import { ArrowLeft, Bot, Plus, SendHorizonal, UserRound, Wrench } from "lucide-react";
import { useState } from "react";
import AuthGuard from "../../components/auth/AuthGuard";
import { useAuth } from "../../components/auth/AuthProvider";
import ThemeToggle from "../../components/theme/ThemeToggle";

const TOOL_OPTIONS = [
  { id: "research", label: "Research" },
  { id: "generate_content", label: "Generate Content" },
  { id: "post_to_channel", label: "Post to Channel" },
  { id: "full_workflow", label: "Full Workflow" },
];

const INITIAL_ASSISTANT_MESSAGE = {
  id: "assistant-welcome",
  role: "assistant",
  content: "Hello. I am your campaign assistant. Ask for positioning, channel mix, or next actions.",
};

function buildAssistantReply(input, selectedToolLabel) {
  const normalized = input.trim();
  if (!normalized) {
    return "Share a campaign question and I will help shape your next step.";
  }

  return `Tool: ${selectedToolLabel}. Based on "${normalized}", I suggest testing one geo-targeted variant, one high-intent channel, and one concise CTA first.`;
}

function formatChatTitle(input) {
  const trimmed = input.trim();
  if (!trimmed) {
    return "Untitled conversation";
  }

  const words = trimmed.split(/\s+/).slice(0, 5).join(" ");
  return words.length < trimmed.length ? `${words}...` : words;
}

function createConversation() {
  return {
    id: crypto.randomUUID(),
    title: "New conversation",
    tool: "full_workflow",
    updatedAt: Date.now(),
    messages: [
      {
        ...INITIAL_ASSISTANT_MESSAGE,
        id: crypto.randomUUID(),
      },
    ],
  };
}

export default function ChatPage() {
  const { user } = useAuth();
  const [input, setInput] = useState("");
  const [conversations, setConversations] = useState([createConversation()]);
  const [activeConversationId, setActiveConversationId] = useState(conversations[0].id);
  const [selectedTool, setSelectedTool] = useState("full_workflow");

  const activeConversation = conversations.find((conversation) => conversation.id === activeConversationId) || conversations[0];

  function createNewConversation() {
    const nextConversation = createConversation();
    setConversations((prev) => [nextConversation, ...prev]);
    setActiveConversationId(nextConversation.id);
    setSelectedTool(nextConversation.tool);
    setInput("");
  }

  function openConversation(conversationId) {
    const conversation = conversations.find((item) => item.id === conversationId);
    if (!conversation) {
      return;
    }

    setActiveConversationId(conversationId);
    setSelectedTool(conversation.tool);
  }

  function sendMessage(e) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || !activeConversation) {
      return;
    }

    const selectedToolLabel = TOOL_OPTIONS.find((tool) => tool.id === selectedTool)?.label || "Full Workflow";

    const userMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
      tool: selectedToolLabel,
    };

    const assistantMessage = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: buildAssistantReply(trimmed, selectedToolLabel),
    };

    setConversations((prev) =>
      prev
        .map((conversation) => {
          if (conversation.id !== activeConversation.id) {
            return conversation;
          }

          return {
            ...conversation,
            title: conversation.messages.length <= 1 ? formatChatTitle(trimmed) : conversation.title,
            tool: selectedTool,
            updatedAt: Date.now(),
            messages: [...conversation.messages, userMessage, assistantMessage],
          };
        })
        .sort((a, b) => b.updatedAt - a.updatedAt)
    );
    setInput("");
  }

  return (
    <AuthGuard>
      <main className="mx-auto w-full max-w-6xl px-4 py-6 md:py-10">
        <header className="glass-panel mb-6 flex flex-wrap items-center justify-between gap-4 rounded-2xl px-5 py-4">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-brand-300">Conversation Console</p>
            <h1 className="text-main mt-1 text-xl font-bold md:text-2xl">Xynera Chat Interface</h1>
            <p className="text-soft mt-1 text-sm">Signed in as {user?.name || "operator"}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <ThemeToggle />
            <Link href="/workspace" className="btn-ghost">
              <ArrowLeft className="h-4 w-4" />
              Back to workspace
            </Link>
          </div>
        </header>

        <section className="grid gap-4 lg:grid-cols-[260px_1fr]">
          <aside className="glass-panel rounded-2xl p-3 md:p-4">
            <button type="button" onClick={createNewConversation} className="btn-primary mb-3 w-full">
              <Plus className="h-4 w-4" />
              New chat
            </button>
            <div className="space-y-2">
              {conversations.map((conversation) => {
                const isActive = conversation.id === activeConversation?.id;
                const toolLabel = TOOL_OPTIONS.find((tool) => tool.id === conversation.tool)?.label || "Full Workflow";
                return (
                  <button
                    key={conversation.id}
                    type="button"
                    onClick={() => openConversation(conversation.id)}
                    className={`w-full rounded-xl border px-3 py-2 text-left transition ${
                      isActive
                        ? "border-brand-400/70 bg-brand-400/15"
                        : "border-slate-500/40 bg-black/10 hover:border-brand-400/40 hover:bg-brand-400/10"
                    }`}
                  >
                    <p className="text-main truncate text-sm font-semibold">{conversation.title}</p>
                    <p className="text-muted mt-1 truncate text-xs">{toolLabel}</p>
                  </button>
                );
              })}
            </div>
          </aside>

          <div className="glass-panel rounded-2xl p-4 md:p-6">
            <div className="space-y-3 rounded-2xl border border-slate-500/30 bg-black/10 p-3 md:p-4">
              {activeConversation?.messages.map((message) => {
                const isUser = message.role === "user";
                return (
                  <article
                    key={message.id}
                    className={`flex items-start gap-3 rounded-xl border p-3 ${
                      isUser ? "ml-auto max-w-[85%] border-brand-300/30 bg-brand-400/10" : "mr-auto max-w-[92%] border-slate-500/30 bg-white/40"
                    }`}
                  >
                    <span className="mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-full bg-slate-900/90 text-brand-200">
                      {isUser ? <UserRound className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                    </span>
                    <div>
                      {isUser && message.tool ? <p className="text-muted mb-1 text-[11px] uppercase tracking-[0.14em]">{message.tool}</p> : null}
                      <p className="text-main text-sm leading-relaxed">{message.content}</p>
                    </div>
                  </article>
                );
              })}
            </div>

            <form onSubmit={sendMessage} className="mt-4 flex flex-col gap-3">
              <div className="flex flex-col gap-3 md:flex-row md:items-center">
                <label className="text-soft inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em]">
                  <Wrench className="h-3.5 w-3.5" />
                  Tool
                </label>
                <select
                  className="input-field md:max-w-xs"
                  value={selectedTool}
                  onChange={(event) => setSelectedTool(event.target.value)}
                >
                  {TOOL_OPTIONS.map((tool) => (
                    <option key={tool.id} value={tool.id}>
                      {tool.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex flex-col gap-3 md:flex-row">
                <input
                  className="input-field"
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  placeholder="Ask about campaign strategy, ad variants, or outreach priorities..."
                />
                <button type="submit" className="btn-primary min-w-36">
                  <SendHorizonal className="h-4 w-4" />
                  Send
                </button>
              </div>
            </form>
          </div>
        </section>
      </main>
    </AuthGuard>
  );
}
