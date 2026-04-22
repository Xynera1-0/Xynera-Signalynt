"use client";

import Link from "next/link";
import {
  ArrowLeft,
  Bot,
  Plus,
  SendHorizonal,
  UserRound,
  Wrench,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import AuthGuard from "../../components/auth/AuthGuard";
import { useAuth } from "../../components/auth/AuthProvider";
import EphemeralRenderer from "../../components/ephemeral/EphemeralRenderer";
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
  content:
    "Hello. I am your campaign assistant. Ask for positioning, channel mix, or next actions.",
  uiType: "text",
  intentDetected: "full_workflow",
  signalIds: [],
  metadata: {},
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
  const { user, accessToken, apiGet, apiPost } = useAuth();
  const [input, setInput] = useState("");
  const [conversations, setConversations] = useState([createConversation()]);
  const [activeConversationId, setActiveConversationId] = useState(
    conversations[0].id,
  );
  const [selectedTool, setSelectedTool] = useState("full_workflow");
  const [isSending, setIsSending] = useState(false);
  const [sendError, setSendError] = useState(null);

  const activeConversation = useMemo(
    () =>
      conversations.find(
        (conversation) => conversation.id === activeConversationId,
      ) || conversations[0],
    [activeConversationId, conversations],
  );

  useEffect(() => {
    let cancelled = false;

    async function loadHistory() {
      if (!accessToken) {
        return;
      }

      try {
        const listPayload = await apiGet("/chat/conversations");
        const remoteConversations = listPayload.conversations || [];

        if (!remoteConversations.length) {
          return;
        }

        const withMessages = await Promise.all(
          remoteConversations.map(async (conversation) => {
            const messagesPayload = await apiGet(
              `/chat/conversations/${conversation.id}/messages`,
            );
            const messages = (messagesPayload.messages || []).map((item) => ({
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
              id: conversation.id,
              title: conversation.title,
              tool: conversation.tool || "full_workflow",
              updatedAt: conversation.updated_at
                ? new Date(conversation.updated_at).getTime()
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
          setSelectedTool(ordered[0].tool || "full_workflow");
        }
      } catch {
        // Keep in-memory fallback if history fetch fails.
      }
    }

    loadHistory();
    return () => {
      cancelled = true;
    };
  }, [accessToken, apiGet]);

  function createNewConversation() {
    const nextConversation = createConversation();
    setConversations((prev) => [nextConversation, ...prev]);
    setActiveConversationId(nextConversation.id);
    setSelectedTool(nextConversation.tool);
    setInput("");
  }

  function openConversation(conversationId) {
    const conversation = conversations.find(
      (item) => item.id === conversationId,
    );
    if (!conversation) {
      return;
    }

    setActiveConversationId(conversationId);
    setSelectedTool(conversation.tool);
  }

  function formatAgentResponse(result) {
    if (!result) return "No response returned.";
    if (typeof result === "string") return result;
    return JSON.stringify(result, null, 2);
  }

  async function sendMessage(e) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || !activeConversation) return;

    const conversationId = activeConversation.id;
    const conversationTitle =
      activeConversation.messages.length <= 1
        ? formatChatTitle(trimmed)
        : activeConversation.title;

    const selectedToolLabel =
      TOOL_OPTIONS.find((t) => t.id === selectedTool)?.label || selectedTool;
    const shouldRunAgent = !!accessToken;

    // Optimistic user bubble
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
      content: "Running agent…",
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
        await apiPost("/chat/conversations", {
          id: conversationId,
          title: conversationTitle,
          tool: selectedTool,
        });

        await apiPost(`/chat/conversations/${conversationId}/messages`, {
          id: optimisticUserMsg.id,
          role: "user",
          content: optimisticUserMsg.content,
          tool: selectedTool,
          ui_type: optimisticUserMsg.uiType,
          intent_detected: optimisticUserMsg.intentDetected,
          signal_ids: optimisticUserMsg.signalIds,
          metadata: optimisticUserMsg.metadata,
        });
      }

      if (shouldRunAgent) {
        const payload = {
          prompt: trimmed,
          audience: user?.name || user?.email || "operator",
          goal: "Generate marketing content from the user prompt",
          tone: "Modern and persuasive",
          platform: selectedToolLabel,
          insights:
            "Use the prompt as the primary creative brief and keep the output concise.",
          extra_context: {
            prompt: trimmed,
            user: user?.email || user?.name || "anonymous",
          },
        };

        const response = await apiPost(
          "/agents/content-generation/run",
          payload,
        );
        const rendered = formatAgentResponse(response.result);
        const flyerImage = response.flyer_image;
        const flyerImageDataUrl = flyerImage?.base64
          ? `data:${flyerImage.mime_type || "image/jpeg"};base64,${flyerImage.base64}`
          : null;

        setConversations((prev) =>
          prev
            .map((conversation) => {
              if (conversation.id !== conversationId) {
                return conversation;
              }

              const nextMessages = [...conversation.messages];
              nextMessages[nextMessages.length - 1] = {
                ...nextMessages[nextMessages.length - 1],
                content: rendered,
                result: response.result,
                flyerImageUrl: flyerImageDataUrl,
                flyerImageSourceUrl: flyerImage?.source_url || null,
                uiType: flyerImageDataUrl ? "flyer" : "content_bundle",
                intentDetected: selectedTool,
                signalIds: response.result?.signal_ids || [],
                metadata: {
                  flyer_image_source_url: flyerImage?.source_url || null,
                  agent_result: response.result,
                },
              };

              return {
                ...conversation,
                title: conversationTitle,
                tool: selectedTool,
                updatedAt: Date.now(),
                messages: nextMessages,
              };
            })
            .sort((a, b) => b.updatedAt - a.updatedAt),
        );

        if (accessToken) {
          await apiPost(`/chat/conversations/${conversationId}/messages`, {
            id: optimisticAssistantMsg.id,
            role: "assistant",
            content: rendered,
            tool: selectedToolLabel,
            ui_type: flyerImageDataUrl ? "flyer" : "content_bundle",
            intent_detected: selectedTool,
            signal_ids: response.result?.signal_ids || [],
            metadata: {
              flyer_image_source_url: flyerImage?.source_url || null,
              agent_result: response.result,
            },
          });
        }
      } else {
        setConversations((prev) =>
          prev
            .map((conversation) => {
              if (conversation.id !== conversationId) {
                return conversation;
              }

              const nextMessages = [...conversation.messages];
              nextMessages[nextMessages.length - 1] = {
                ...nextMessages[nextMessages.length - 1],
                content: buildAssistantReply(trimmed, selectedToolLabel),
                uiType: "text",
                intentDetected: selectedTool,
                signalIds: [],
                metadata: {},
              };
              return {
                ...conversation,
                title: conversationTitle,
                tool: selectedTool,
                updatedAt: Date.now(),
                messages: nextMessages,
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
      <main className="mx-auto w-full max-w-6xl px-4 py-6 md:py-10">
        <header className="glass-panel mb-6 flex flex-wrap items-center justify-between gap-4 rounded-2xl px-5 py-4">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-brand-300">
              Conversation Console
            </p>
            <h1 className="text-main mt-1 text-xl font-bold md:text-2xl">
              Xynera Chat Interface
            </h1>
            <p className="text-soft mt-1 text-sm">
              Signed in as {user?.name || "operator"}
            </p>
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
            <button
              type="button"
              onClick={createNewConversation}
              className="btn-primary mb-3 w-full"
            >
              <Plus className="h-4 w-4" />
              New chat
            </button>
            <div className="space-y-2">
              {conversations.map((conversation) => {
                const isActive = conversation.id === activeConversation?.id;
                const toolLabel =
                  TOOL_OPTIONS.find((tool) => tool.id === conversation.tool)
                    ?.label || "Full Workflow";
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
                    <p className="text-main truncate text-sm font-semibold">
                      {conversation.title}
                    </p>
                    <p className="text-muted mt-1 truncate text-xs">
                      {toolLabel}
                    </p>
                  </button>
                );
              })}
            </div>
          </aside>

          <div className="glass-panel rounded-2xl p-4 md:p-6">
            <div className="space-y-3 rounded-2xl border border-slate-500/30 bg-black/10 p-3 md:p-4">
              {activeConversation?.messages.map((message) => {
                const isUser = message.role === "user";
                // Assistant messages with a rich ui_type get a full-width card,
                // user messages and plain text get the standard bubble layout
                const hasRichUI =
                  !isUser &&
                  message.uiType &&
                  message.uiType !== "text" &&
                  message.uiType !== "prompt";
                return (
                  <article
                    key={message.id}
                    className={
                      hasRichUI
                        ? "mr-auto w-full"
                        : `flex items-start gap-3 rounded-xl border p-3 ${
                            isUser
                              ? "ml-auto max-w-[85%] border-brand-300/30 bg-brand-400/10"
                              : "mr-auto max-w-[92%] border-slate-500/30 bg-white/40"
                          }`
                    }
                  >
                    {!hasRichUI && (
                      <span className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-900/90 text-brand-200">
                        {isUser ? (
                          <UserRound className="h-4 w-4" />
                        ) : (
                          <Bot className="h-4 w-4" />
                        )}
                      </span>
                    )}
                    <div className="min-w-0 flex-1">
                      {isUser && message.tool ? (
                        <p className="text-muted mb-1 text-[11px] uppercase tracking-[0.14em]">
                          {message.tool}
                        </p>
                      ) : null}
                      {hasRichUI ? (
                        <EphemeralRenderer
                          message={{
                            ...message,
                            ui_payload:
                              message.ui_payload || message.metadata || {},
                          }}
                          onAction={(action) => setInput(action)}
                        />
                      ) : typeof message.content === "string" ? (
                        <p className="text-main whitespace-pre-wrap text-sm leading-relaxed">
                          {message.content}
                        </p>
                      ) : (
                        <pre className="text-main overflow-x-auto whitespace-pre-wrap text-xs leading-relaxed">
                          {JSON.stringify(message.content, null, 2)}
                        </pre>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>

            {sendError ? (
              <p className="mt-3 rounded-xl border border-rose-400/25 bg-rose-400/10 px-3 py-2 text-sm text-rose-200">
                {sendError}
              </p>
            ) : null}

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
                <button
                  type="submit"
                  className="btn-primary min-w-36"
                  disabled={isSending}
                >
                  <SendHorizonal className="h-4 w-4" />
                  {isSending ? "Running..." : "Send"}
                </button>
              </div>
            </form>
          </div>
        </section>
      </main>
    </AuthGuard>
  );
}
