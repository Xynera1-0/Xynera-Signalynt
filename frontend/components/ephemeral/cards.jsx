"use client";

import {
  ArrowUpRight,
  BarChart3,
  CircleGauge,
  CheckCircle2,
  Clock,
  Sparkles,
} from "lucide-react";

export function SignalMap({ data }) {
  return (
    <div className="card animate-slide-up">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm font-semibold text-brand-200">{data.territory}</p>
        <span className="rounded-full bg-brand-400/10 px-2.5 py-1 text-xs text-brand-200">
          Live intelligence
        </span>
      </div>
      <div className="space-y-3">
        {(data.signals || []).map((signal) => (
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
      {data.full_report && (
        <details className="mt-4">
          <summary className="cursor-pointer text-xs text-slate-400 hover:text-brand-300">
            Full report
          </summary>
          <p className="mt-2 whitespace-pre-wrap text-xs text-slate-300">
            {data.full_report}
          </p>
        </details>
      )}
    </div>
  );
}

export function VariantComparisonGrid({ data, onSelect }) {
  return (
    <div className="card animate-slide-up">
      <div className="mb-4 flex items-center gap-2 text-main">
        <BarChart3 className="h-4 w-4 text-brand-300" />
        <p className="text-sm font-semibold">Creative variant comparison</p>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        {(data.variants || []).map((variant) => (
          <button
            key={variant.name}
            type="button"
            onClick={() => onSelect?.(variant.name)}
            className="group rounded-xl border p-4 text-left transition hover:border-brand-400/40"
            style={{
              borderColor: "var(--card-border)",
              background: "var(--card-bg)",
            }}
          >
            <div className="flex items-center justify-between">
              <p className="text-main text-sm font-semibold">{variant.name}</p>
              {variant.is_control && (
                <span className="rounded-full bg-slate-700 px-2 py-0.5 text-xs text-slate-300">
                  Control
                </span>
              )}
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
            <p className="mt-3 inline-flex items-center gap-1 text-xs text-brand-300 opacity-0 transition group-hover:opacity-100">
              Choose variant <ArrowUpRight className="h-3 w-3" />
            </p>
          </button>
        ))}
      </div>
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
