"use client";

import Link from "next/link";
import { ArrowLeft, Bot, Plus, SendHorizonal, UserRound, Wrench } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
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
  uiType: "text",
  intentDetected: "full_workflow",
  signalIds: [],
  metadata: {},
};

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

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

async function postJson(path, body, accessToken) {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify(body),
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || "Request failed");
  }

  return payload;
}

async function getJson(path, accessToken) {
  const response = await fetch(`${API_URL}${path}`, {
    method: "GET",
    headers: {
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || "Request failed");
  }

  return payload;
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
  const { user, accessToken } = useAuth();
  const [input, setInput] = useState("");
  const [conversations, setConversations] = useState([createConversation()]);
  const [activeConversationId, setActiveConversationId] = useState(conversations[0].id);
  const [selectedTool, setSelectedTool] = useState("full_workflow");
  const [isSending, setIsSending] = useState(false);
  const [sendError, setSendError] = useState(null);

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === activeConversationId) || conversations[0],
    [activeConversationId, conversations]
  );

  useEffect(() => {
    let cancelled = false;

    async function loadHistory() {
      if (!accessToken) {
        return;
      }

      try {
        const listPayload = await getJson("/chat/conversations", accessToken);
        const remoteConversations = listPayload.conversations || [];

        if (!remoteConversations.length) {
          return;
        }

        const withMessages = await Promise.all(
          remoteConversations.map(async (conversation) => {
            const messagesPayload = await getJson(`/chat/conversations/${conversation.id}/messages`, accessToken);
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
              updatedAt: conversation.updated_at ? new Date(conversation.updated_at).getTime() : Date.now(),
              messages: messages.length ? messages : [{ ...INITIAL_ASSISTANT_MESSAGE, id: crypto.randomUUID() }],
            };
          })
        );

        if (!cancelled) {
          const ordered = withMessages.sort((a, b) => b.updatedAt - a.updatedAt);
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
  }, [accessToken]);

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

  function formatAgentResponse(result) {
    if (!result) {
      return "No response returned.";
    }

    if (typeof result === "string") {
      return result;
    }

    const content = result.content || {};
    const critique = result.critique || {};

    if (content.headlines || content.body || content.cta || critique.final_output) {
      const lines = [];

      if (content.headlines?.length) {
        lines.push(`Headlines:\n- ${content.headlines.join("\n- ")}`);
      }

      if (content.body) {
        lines.push(`Body:\n${content.body}`);
      }

      if (content.cta) {
        lines.push(`CTA:\n${content.cta}`);
      }

      if (critique.final_output) {
        lines.push(`Final:\n${critique.final_output}`);
      } else if (content.platform_output) {
        lines.push(`Platform Output:\n${content.platform_output}`);
      }

      return lines.join("\n\n");
    }

    return JSON.stringify(result, null, 2);
  }

  async function sendMessage(e) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || !activeConversation) {
      return;
    }

    const selectedToolLabel = TOOL_OPTIONS.find((tool) => tool.id === selectedTool)?.label || "Full Workflow";
    const conversationId = activeConversation.id;
    const shouldRunAgent = selectedTool === "generate_content" || selectedTool === "full_workflow";
    const conversationTitle = activeConversation.messages.length <= 1 ? formatChatTitle(trimmed) : activeConversation.title;

    const userMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
      tool: selectedToolLabel,
      uiType: "prompt",
      intentDetected: selectedTool,
      signalIds: [],
      metadata: {
        prompt: trimmed,
        tool: selectedTool,
      },
    };

    const assistantMessage = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: shouldRunAgent ? "Running content generation agent..." : buildAssistantReply(trimmed, selectedToolLabel),
      uiType: shouldRunAgent ? "content_bundle" : "text",
      intentDetected: selectedTool,
      signalIds: [],
      metadata: {},
    };

    setIsSending(true);
    setSendError(null);
    setConversations((prev) =>
      prev
        .map((conversation) => {
          if (conversation.id !== conversationId) {
            return conversation;
          }

          return {
            ...conversation,
            title: conversationTitle,
            tool: selectedTool,
            updatedAt: Date.now(),
            messages: [...conversation.messages, userMessage, assistantMessage],
          };
        })
        .sort((a, b) => b.updatedAt - a.updatedAt)
    );

    try {
      if (accessToken) {
        await postJson(
          "/chat/conversations",
          {
            id: conversationId,
            title: conversationTitle,
            tool: selectedTool,
          },
          accessToken
        );

        await postJson(
          `/chat/conversations/${conversationId}/messages`,
          {
            id: userMessage.id,
            role: "user",
            content: userMessage.content,
            tool: userMessage.tool,
            ui_type: userMessage.uiType,
            intent_detected: userMessage.intentDetected,
            signal_ids: userMessage.signalIds,
            metadata: userMessage.metadata,
          },
          accessToken
        );
      }

      if (shouldRunAgent) {
        const payload = {
          prompt: trimmed,
          audience: user?.name || user?.email || "operator",
          goal: "Generate marketing content from the user prompt",
          tone: "Modern and persuasive",
          platform: selectedToolLabel,
          insights: "Use the prompt as the primary creative brief and keep the output concise.",
          extra_context: {
            prompt: trimmed,
            user: user?.email || user?.name || "anonymous",
          },
        };

        const response = await postJson("/agents/content-generation/run", payload, accessToken);
        const rendered = formatAgentResponse(response.result);
        const flyerImage = response.flyer_image;
        const flyerImageDataUrl = flyerImage?.base64
          ? `data:${flyerImage.mime_type || "image/jpeg"};base64,${flyerImage.base64}`
          : null;

        setConversations((prev) =>
          prev.map((conversation) => {
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
          }).sort((a, b) => b.updatedAt - a.updatedAt)
        );

        if (accessToken) {
          await postJson(
            `/chat/conversations/${conversationId}/messages`,
            {
              id: assistantMessage.id,
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
            },
            accessToken
          );
        }
      } else {
        setConversations((prev) =>
          prev.map((conversation) => {
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
          }).sort((a, b) => b.updatedAt - a.updatedAt)
        );

        if (accessToken) {
          await postJson(
            `/chat/conversations/${conversationId}/messages`,
            {
              id: assistantMessage.id,
              role: "assistant",
              content: buildAssistantReply(trimmed, selectedToolLabel),
              tool: selectedToolLabel,
              ui_type: "text",
              intent_detected: selectedTool,
              signal_ids: [],
              metadata: {},
            },
            accessToken
          );
        }
      }

      setInput("");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Agent request failed.";
      setSendError(message);
      setConversations((prev) =>
        prev.map((conversation) => {
          if (conversation.id !== conversationId) {
            return conversation;
          }

          const nextMessages = [...conversation.messages];
          nextMessages[nextMessages.length - 1] = {
            ...nextMessages[nextMessages.length - 1],
            content: `Agent request failed: ${message}`,
          };

          return {
            ...conversation,
            updatedAt: Date.now(),
            messages: nextMessages,
          };
        }).sort((a, b) => b.updatedAt - a.updatedAt)
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
                    <div className="min-w-0 flex-1">
                      {isUser && message.tool ? <p className="text-muted mb-1 text-[11px] uppercase tracking-[0.14em]">{message.tool}</p> : null}
                      {typeof message.content === "string" ? (
                        <p className="text-main whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
                      ) : (
                        <pre className="text-main overflow-x-auto whitespace-pre-wrap text-xs leading-relaxed">{JSON.stringify(message.content, null, 2)}</pre>
                      )}
                      {message.flyerImageUrl ? (
                        <div className="mt-3 overflow-hidden rounded-xl border border-slate-500/30 bg-black/5 p-2">
                          <img
                            src={message.flyerImageUrl}
                            alt="Generated flyer"
                            className="h-auto w-full rounded-lg object-contain"
                            loading="lazy"
                          />
                          {message.flyerImageSourceUrl ? (
                            <p className="text-muted mt-2 break-all text-[11px]">Image source: {message.flyerImageSourceUrl}</p>
                          ) : null}
                        </div>
                      ) : null}
                      {message.uiType ? <p className="text-muted mt-2 text-[11px] uppercase tracking-[0.14em]">{message.uiType}</p> : null}
                    </div>
                  </article>
                );
              })}
            </div>

            {sendError ? <p className="mt-3 rounded-xl border border-rose-400/25 bg-rose-400/10 px-3 py-2 text-sm text-rose-200">{sendError}</p> : null}

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
                <button type="submit" className="btn-primary min-w-36" disabled={isSending}>
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
