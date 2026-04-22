"use client";

import { useState } from "react";
import {
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  CircleGauge,
  Clock,
  Download,
  Sparkles,
} from "lucide-react";

export function FlyerCard({ data, onExpand }) {
  const { flyerImageUrl, result } = data;
  const content = result?.content || {};
  const critique = result?.critique || {};
  const headlines = content.headlines || [];
  const bestHeadline = headlines[0] || "Generated flyer";
  const cta = content.cta || "";
  const finalOutput = critique.final_output || "";

  const flyerData = { flyerImageUrl, content, critique };

  return (
    /* Matches the reference design card */
    <div className="overflow-hidden rounded-xl border border-slate-800 bg-[#171f33] shadow-2xl max-w-[500px] animate-slide-up">
      {/* Card header */}
      <div className="flex items-center justify-between border-b border-slate-800 bg-slate-900/50 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-lg text-teal-400">
            design_services
          </span>
          <span className="text-[11px] font-bold uppercase tracking-widest text-teal-400">
            Generated Flyer
          </span>
        </div>
        <div className="flex gap-1">
          {flyerImageUrl && (
            <a
              href={flyerImageUrl}
              download="flyer.jpg"
              target="_blank"
              rel="noreferrer"
              className="rounded p-1.5 text-slate-400 transition hover:bg-slate-800"
              title="Download"
            >
              <Download className="h-[18px] w-[18px]" />
            </a>
          )}
          {onExpand && (
            <button
              type="button"
              onClick={() => onExpand(flyerData)}
              className="rounded p-1.5 text-slate-400 transition hover:bg-slate-800"
              title="Full view"
            >
              <span className="material-symbols-outlined text-[18px]">
                open_in_full
              </span>
            </button>
          )}
        </div>
      </div>

      {/* Clickable image with gradient + text overlay */}
      <div className="relative group bg-[#0b1326]">
        <button
          type="button"
          onClick={() => onExpand?.(flyerData)}
          className="block w-full text-left"
        >
          {flyerImageUrl ? (
            <img
              src={flyerImageUrl}
              alt={bestHeadline}
              className="h-[360px] w-full object-cover opacity-90 transition-transform duration-500 group-hover:scale-[1.02]"
            />
          ) : (
            <div className="flex h-[260px] items-center justify-center bg-[#131b2e]">
              <p className="text-xs text-slate-500">Image unavailable</p>
            </div>
          )}

          {/* Gradient */}
          <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-transparent to-transparent" />

          {/* Overlaid text */}
          <div className="absolute inset-0 flex flex-col justify-end p-6">
            {bestHeadline && (
              <h3
                className="mb-1 text-2xl font-black leading-tight text-white"
                style={{ textShadow: "0 2px 12px rgba(0,0,0,0.9)" }}
              >
                {bestHeadline}
              </h3>
            )}
            {cta && <p className="text-sm font-bold text-teal-400">{cta}</p>}
            <div className="mt-2 h-1 w-10 rounded-full bg-teal-400" />
          </div>

          {/* Open hint */}
          <div className="absolute right-3 top-3 flex items-center gap-1 rounded-lg bg-black/60 px-2 py-1 opacity-0 transition group-hover:opacity-100">
            <span className="material-symbols-outlined text-sm text-white">
              open_in_full
            </span>
            <span className="text-[10px] text-white">Full view</span>
          </div>
        </button>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between bg-slate-900/30 px-4 py-3">
        <span className="text-[11px] text-slate-400">
          Ready for distribution (A4 / 300DPI)
        </span>
        <span className="rounded border border-teal-400/20 bg-teal-400/10 px-2 py-0.5 text-[10px] font-bold text-teal-400">
          HD RENDER
        </span>
      </div>

      {/* Final copy collapsible */}
      {finalOutput && (
        <details className="border-t border-slate-800 bg-[#131b2e] px-4 py-2">
          <summary className="cursor-pointer text-[11px] text-slate-400 hover:text-teal-400">
            Critique &amp; final copy
          </summary>
          <p className="mt-2 whitespace-pre-wrap text-xs text-slate-300">
            {finalOutput}
          </p>
        </details>
      )}
    </div>
  );
}

const TYPE_LABELS = {
  email: "Email",
  post: "Social Post",
  slogan: "Slogans & Taglines",
  strategy: "Strategy Plan",
  blog: "Blog Article",
};

function ContentSection({ label, children }) {
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-3">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-brand-300">
        {label}
      </p>
      {children}
    </div>
  );
}

export function ContentCard({ data }) {
  const { result } = data;
  if (!result) return null;

  const contentType = result.content_type || "content";
  const content = result.content || {};
  const critique = result.critique || {};
  const typeLabel = TYPE_LABELS[contentType] || "Generated Content";

  // Helpers
  const renderList = (arr) =>
    Array.isArray(arr)
      ? arr.map((item, i) => (
          <li key={i} className="text-sm text-main">
            • {typeof item === "string" ? item : JSON.stringify(item)}
          </li>
        ))
      : null;

  const renderStringMap = (obj) =>
    obj && typeof obj === "object"
      ? Object.entries(obj).map(([k, v]) => (
          <div key={k} className="mb-2">
            <p className="text-[11px] font-semibold capitalize text-slate-400">
              {k.replace(/_/g, " ")}
            </p>
            <p className="text-sm text-main">
              {typeof v === "string" ? v : JSON.stringify(v)}
            </p>
          </div>
        ))
      : null;

  return (
    <div className="card animate-slide-up space-y-3">
      <div className="flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-brand-300" />
        <p className="text-sm font-semibold text-main">{typeLabel}</p>
      </div>

      {/* Email */}
      {contentType === "email" && (
        <>
          {content.subject_lines?.length > 0 && (
            <ContentSection label="Subject lines">
              <ul className="space-y-1">{renderList(content.subject_lines)}</ul>
            </ContentSection>
          )}
          {content.body && typeof content.body === "object" && (
            <ContentSection label="Body">
              {renderStringMap(content.body)}
            </ContentSection>
          )}
          {content.cta && (
            <p className="text-xs text-slate-300">
              <span className="font-semibold text-amber-400">CTA: </span>
              {content.cta}
            </p>
          )}
          {content.ps_line && (
            <p className="text-xs text-slate-400 italic">
              P.S. {content.ps_line}
            </p>
          )}
        </>
      )}

      {/* Social Post */}
      {contentType === "post" && (
        <>
          {(content.posts || []).map((post, i) => (
            <ContentSection key={i} label={`${post.angle} angle`}>
              <p className="whitespace-pre-wrap text-sm text-main">
                {post.copy}
              </p>
              {post.hashtags?.length > 0 && (
                <p className="mt-1 text-xs text-brand-300">
                  {post.hashtags.join(" ")}
                </p>
              )}
            </ContentSection>
          ))}
          {content.thread_version && (
            <details>
              <summary className="cursor-pointer text-xs text-slate-400 hover:text-brand-300">
                Thread version
              </summary>
              <p className="mt-2 whitespace-pre-wrap text-xs text-slate-300">
                {content.thread_version}
              </p>
            </details>
          )}
        </>
      )}

      {/* Slogans */}
      {contentType === "slogan" && (
        <>
          <ContentSection label="Slogans">
            <ul className="space-y-2">
              {(content.slogans || []).map((slogan, i) => (
                <li key={i}>
                  <p className="text-sm font-semibold text-main">{slogan}</p>
                  {content.rationale?.[i] && (
                    <p className="text-xs text-slate-400">
                      {content.rationale[i]}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </ContentSection>
          {content.best_slogan && (
            <div className="rounded-xl border border-emerald-900/40 bg-emerald-950/20 p-3">
              <p className="text-xs font-semibold text-emerald-300">
                Best pick
              </p>
              <p className="mt-1 text-sm font-bold text-main">
                {content.best_slogan}
              </p>
              {content.why && (
                <p className="mt-1 text-xs text-slate-400">{content.why}</p>
              )}
            </div>
          )}
        </>
      )}

      {/* Strategy */}
      {contentType === "strategy" && (
        <>
          {content.positioning && (
            <ContentSection label="Positioning">
              {content.positioning}
            </ContentSection>
          )}
          {content.key_messages?.length > 0 && (
            <ContentSection label="Key messages">
              <ul className="space-y-1">{renderList(content.key_messages)}</ul>
            </ContentSection>
          )}
          {content.channel_mix?.length > 0 && (
            <ContentSection label="Channel mix">
              {content.channel_mix.map((ch, i) => (
                <div key={i} className="mb-2 flex items-start gap-2">
                  <span className="mt-0.5 rounded bg-brand-400/20 px-1.5 py-0.5 text-[10px] font-semibold text-brand-300">
                    {ch.priority}
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-main">
                      {ch.channel}
                    </p>
                    <p className="text-xs text-slate-400">{ch.rationale}</p>
                  </div>
                </div>
              ))}
            </ContentSection>
          )}
          {content.quick_wins?.length > 0 && (
            <ContentSection label="Quick wins">
              <ul className="space-y-1">{renderList(content.quick_wins)}</ul>
            </ContentSection>
          )}
        </>
      )}

      {/* Blog */}
      {contentType === "blog" && (
        <>
          {content.title && (
            <p className="text-base font-bold text-main">{content.title}</p>
          )}
          {content.meta_description && (
            <p className="text-xs text-slate-400 italic">
              {content.meta_description}
            </p>
          )}
          {content.intro && (
            <ContentSection label="Intro">{content.intro}</ContentSection>
          )}
          {content.outline?.length > 0 && (
            <ContentSection label="Outline">
              {content.outline.map((section, i) => (
                <div key={i} className="mb-2">
                  <p className="text-sm font-semibold text-main">
                    {section.section}
                  </p>
                  <ul className="space-y-0.5">
                    {renderList(section.key_points)}
                  </ul>
                </div>
              ))}
            </ContentSection>
          )}
          {content.cta && (
            <p className="text-xs text-slate-300">
              <span className="font-semibold text-amber-400">CTA: </span>
              {content.cta}
            </p>
          )}
        </>
      )}

      {/* Critique / final copy */}
      {critique.final_output && (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-slate-400 hover:text-brand-300">
            Critique &amp; final version
          </summary>
          <div className="mt-2 space-y-1">
            {critique.reason && (
              <p className="text-xs text-slate-400">{critique.reason}</p>
            )}
            {critique.score != null && (
              <p className="text-xs text-slate-400">
                Score:{" "}
                <span className="text-brand-300">{critique.score}/10</span>
              </p>
            )}
            <p className="whitespace-pre-wrap text-xs text-slate-300">
              {critique.final_output}
            </p>
          </div>
        </details>
      )}
    </div>
  );
}

export function SignalMap({ data }) {
  const confidence = data.confidence ?? null;
  const confidencePct =
    confidence !== null ? Math.round(confidence * 100) : null;

  return (
    <div className="card animate-slide-up space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-lg text-teal-400">
            query_stats
          </span>
          <p className="text-sm font-semibold text-brand-200">Research Brief</p>
        </div>
        {confidencePct !== null && (
          <span className="rounded-full bg-brand-400/10 px-2.5 py-1 text-xs text-brand-200">
            {confidencePct}% confidence
          </span>
        )}
      </div>

      {/* Summary */}
      {data.summary && (
        <p className="text-sm leading-relaxed text-slate-300">{data.summary}</p>
      )}

      {/* Key Insights */}
      {(data.key_insights || []).length > 0 && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-teal-400">
            Key Insights
          </p>
          <ul className="space-y-1.5">
            {data.key_insights.map((insight, i) => (
              <li
                key={i}
                className="flex items-start gap-2 text-xs text-slate-300"
              >
                <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-400" />
                {insight}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Agent Signal Bars */}
      {(data.signals || []).length > 0 && (
        <div className="space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Signal Confidence
          </p>
          {data.signals.map((signal) => (
            <div
              key={signal.label}
              className="rounded-xl border border-slate-800 bg-slate-900/80 p-3"
            >
              <div className="mb-2 flex items-center justify-between text-xs">
                <span className="text-slate-300">{signal.label}</span>
                <span className="text-emerald-300">{signal.trend}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-brand-500 to-emerald-400"
                  style={{ width: `${signal.value}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Gaps */}
      {(data.gaps || []).length > 0 && (
        <details className="rounded-xl border border-slate-800 bg-slate-900/40 px-3 py-2">
          <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-wider text-slate-400 hover:text-brand-300">
            Research Gaps ({data.gaps.length})
          </summary>
          <ul className="mt-2 space-y-1.5">
            {data.gaps.map((gap, i) => (
              <li
                key={i}
                className="flex items-start gap-2 text-xs text-slate-400"
              >
                <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />
                {gap}
              </li>
            ))}
          </ul>
        </details>
      )}

      {/* Sources */}
      {(data.sources || []).length > 0 && (
        <details className="rounded-xl border border-slate-800 bg-slate-900/40 px-3 py-2">
          <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-wider text-slate-400 hover:text-brand-300">
            Sources ({data.sources.length})
          </summary>
          <ul className="mt-2 space-y-1">
            {data.sources.map((src, i) => (
              <li key={i} className="text-xs">
                {src.url ? (
                  <a
                    href={src.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-teal-400 hover:underline"
                  >
                    {src.name || src.url}
                  </a>
                ) : (
                  <span className="text-slate-400">{src.name}</span>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

export function VariantComparisonGrid({ data, onSelect }) {
  const [selected, setSelected] = useState(null);

  function handleSelect(variant) {
    setSelected(variant);
    // Do NOT call onSelect — that would send a new message to the backend.
    // The content is already in the variant payload; we expand it inline.
  }

  const content = selected?.content || {};
  const variations = content.variations || {};

  return (
    <div className="card animate-slide-up">
      <div className="mb-4 flex items-center gap-2 text-main">
        <BarChart3 className="h-4 w-4 text-brand-300" />
        <p className="text-sm font-semibold">Creative variant comparison</p>
      </div>

      {/* Variant selection grid */}
      <div className="grid gap-3 md:grid-cols-3">
        {(data.variants || []).map((variant) => {
          const isSelected = selected?.name === variant.name;
          return (
            <button
              key={variant.name}
              type="button"
              onClick={() => handleSelect(variant)}
              className={`group rounded-xl border p-4 text-left transition ${
                isSelected
                  ? "border-brand-400 bg-brand-400/5 ring-1 ring-brand-400/30"
                  : "hover:border-brand-400/40"
              }`}
              style={
                isSelected
                  ? {}
                  : {
                      borderColor: "var(--card-border)",
                      background: "var(--card-bg)",
                    }
              }
            >
              <div className="flex items-center justify-between">
                <p className="text-main text-sm font-semibold">
                  {variant.name}
                </p>
                <div className="flex items-center gap-1">
                  {isSelected && (
                    <CheckCircle2 className="h-4 w-4 text-brand-300" />
                  )}
                  {variant.is_control && (
                    <span className="rounded-full bg-slate-700 px-2 py-0.5 text-xs text-slate-300">
                      Control
                    </span>
                  )}
                </div>
              </div>
              <div className="text-soft mt-3 space-y-2 text-xs">
                <p>
                  CTR: <span className="text-brand-300">{variant.ctr}%</span>
                </p>
                <p>
                  CVR: <span className="text-brand-300">{variant.cvr}%</span>
                </p>
                <p>
                  Sentiment:{" "}
                  <span className="text-amber-500">{variant.sentiment}</span>
                </p>
                {variant.platform && (
                  <p>
                    Platform:{" "}
                    <span className="text-slate-300">{variant.platform}</span>
                  </p>
                )}
              </div>
              {!isSelected && (
                <p className="mt-3 inline-flex items-center gap-1 text-xs text-brand-300 opacity-0 transition group-hover:opacity-100">
                  View content <ArrowUpRight className="h-3 w-3" />
                </p>
              )}
            </button>
          );
        })}
      </div>

      {/* Inline content panel — shown when a variant is selected */}
      {selected && (
        <div className="mt-5 rounded-xl border border-brand-400/20 bg-[#0f1929] p-4 space-y-3 animate-slide-up">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-brand-300" />
            <p className="text-sm font-semibold text-brand-200">
              {selected.name}
            </p>
            <span className="ml-auto text-[10px] uppercase tracking-widest text-slate-500">
              {selected.platform}
            </span>
          </div>

          {content.headline && (
            <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-3">
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Headline
              </p>
              <p className="text-sm font-bold text-main">{content.headline}</p>
            </div>
          )}

          {content.body && (
            <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-3">
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Body copy
              </p>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-200">
                {content.body}
              </p>
            </div>
          )}

          {content.cta && (
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-amber-400">
                CTA:
              </span>
              <span className="text-sm text-slate-200">{content.cta}</span>
            </div>
          )}

          {Object.keys(variations).length > 0 && (
            <details className="rounded-xl border border-slate-800 bg-slate-900/40 px-3 py-2">
              <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-wider text-slate-400 hover:text-brand-300">
                Tone variations
              </summary>
              <div className="mt-3 space-y-3">
                {Object.entries(variations).map(([tone, copy]) => (
                  <div key={tone}>
                    <p className="text-[10px] font-semibold capitalize text-slate-500">
                      {tone}
                    </p>
                    <p className="text-xs text-slate-300">{copy}</p>
                  </div>
                ))}
              </div>
            </details>
          )}

          {content.platform_output && (
            <details className="rounded-xl border border-slate-800 bg-slate-900/40 px-3 py-2">
              <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-wider text-slate-400 hover:text-brand-300">
                Platform output
              </summary>
              <p className="mt-2 whitespace-pre-wrap text-xs text-slate-300">
                {content.platform_output}
              </p>
            </details>
          )}
        </div>
      )}

      {/* Growth signals */}
      {(data.growth_signals || []).length > 0 && (
        <div className="mt-4 rounded-xl border border-emerald-900/40 bg-emerald-950/20 p-3">
          <p className="mb-2 text-xs font-semibold text-emerald-300">
            Growth signals detected
          </p>
          <ul className="space-y-1">
            {data.growth_signals.slice(0, 3).map((s, i) => (
              <li key={i} className="text-xs text-slate-300">
                • {s.description || JSON.stringify(s)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function ChannelSelector({ data, onAction }) {
  return (
    <div className="card animate-slide-up">
      <p className="mb-4 flex items-center gap-2 text-sm font-semibold text-main">
        <Sparkles className="h-4 w-4 text-amber-500" />
        {data.prompt}
      </p>
      <div className="flex flex-wrap gap-3">
        {(data.options || []).map((option) => (
          <button
            key={option}
            className="btn-ghost"
            type="button"
            onClick={() => onAction?.(option)}
          >
            <CircleGauge className="h-4 w-4" />
            Launch via {option}
          </button>
        ))}
      </div>
    </div>
  );
}

export function PublishConfirmation({ data, onConfirm }) {
  const items = data.content_to_post || [];
  const available = data.available_campaigns || [];
  return (
    <div className="card animate-slide-up">
      <div className="mb-4 flex items-center gap-2">
        <Clock className="h-4 w-4 text-amber-400" />
        <p className="text-sm font-semibold text-main">Ready to publish</p>
      </div>
      {data.error ? (
        <div className="rounded-xl border border-red-900/40 bg-red-950/20 p-3">
          <p className="text-xs text-red-300">{data.error}</p>
          {available.length > 0 && (
            <div className="mt-3">
              <p className="mb-2 text-xs text-slate-400">
                Available campaigns:
              </p>
              <ul className="space-y-1">
                {available.map((c, i) => (
                  <li key={i} className="text-xs text-slate-300">
                    • <span className="text-brand-300">{c.name}</span> —{" "}
                    {c.created_at?.slice(0, 10)} (
                    {(c.platforms || []).join(", ")})
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : (
        <>
          <p className="mb-3 text-xs text-slate-300">{data.message}</p>
          <div className="space-y-2">
            {items.map((item) => (
              <div
                key={item.id}
                className="rounded-xl border border-slate-800 bg-slate-900/60 p-3"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-brand-300">
                    {item.platform}
                  </span>
                  <span className="text-xs text-slate-400">
                    {item.content_type}
                  </span>
                </div>
                {item.headline && (
                  <p className="mt-1 text-xs font-semibold text-main">
                    {item.headline}
                  </p>
                )}
                {item.cta && (
                  <p className="mt-1 text-xs text-slate-400">CTA: {item.cta}</p>
                )}
              </div>
            ))}
          </div>
          {items.length > 0 && (
            <button
              type="button"
              className="btn-primary mt-4"
              onClick={() =>
                onConfirm?.(data.campaign_id, data.target_platforms)
              }
            >
              <CheckCircle2 className="h-4 w-4" />
              Confirm & publish
            </button>
          )}
        </>
      )}
    </div>
  );
}
