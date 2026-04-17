"use client";

import Link from "next/link";
import { ArrowLeft, Bot, SendHorizonal, UserRound } from "lucide-react";
import { useState } from "react";
import AuthGuard from "../../components/auth/AuthGuard";
import { useAuth } from "../../components/auth/AuthProvider";
import ThemeToggle from "../../components/theme/ThemeToggle";

function buildAssistantReply(input) {
  const normalized = input.trim();
  if (!normalized) {
    return "Share a campaign question and I will help shape your next step.";
  }

  return `Got it. Based on \"${normalized}\", I suggest testing one geo-targeted variant, one high-intent channel, and one concise CTA first.`;
}

export default function ChatPage() {
  const { user } = useAuth();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([
    {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "Hello. I am your campaign assistant. Ask for positioning, channel mix, or next actions.",
    },
  ]);

  function sendMessage(e) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) {
      return;
    }

    const userMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
    };

    const assistantMessage = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: buildAssistantReply(trimmed),
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
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

        <section className="glass-panel rounded-2xl p-4 md:p-6">
          <div className="space-y-3 rounded-2xl border border-slate-500/30 bg-black/10 p-3 md:p-4">
            {messages.map((message) => {
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
                  <p className="text-main text-sm leading-relaxed">{message.content}</p>
                </article>
              );
            })}
          </div>

          <form onSubmit={sendMessage} className="mt-4 flex flex-col gap-3 md:flex-row">
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
          </form>
        </section>
      </main>
    </AuthGuard>
  );
}
