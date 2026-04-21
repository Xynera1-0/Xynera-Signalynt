"use client";

import { ArrowUpRight, BarChart3, CircleGauge, Sparkles } from "lucide-react";

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
        {data.signals.map((signal) => (
          <div key={signal.label} className="rounded-xl border border-slate-800 bg-slate-900/80 p-3">
            <div className="mb-2 flex items-center justify-between text-xs">
              <span className="text-slate-300">{signal.label}</span>
              <span className="text-emerald-300">{signal.trend}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-800">
              <div className="h-full rounded-full bg-gradient-to-r from-brand-500 to-emerald-400" style={{ width: `${signal.value}%` }} />
            </div>
          </div>
        ))}
      </div>
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
        {data.variants.map((variant) => (
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
            <p className="text-main text-sm font-semibold">{variant.name}</p>
            <div className="text-soft mt-3 space-y-2 text-xs">
              <p>CTR: <span className="text-brand-300">{variant.ctr}%</span></p>
              <p>CVR: <span className="text-brand-300">{variant.cvr}%</span></p>
              <p>Sentiment: <span className="text-amber-500">{variant.sentiment}</span></p>
            </div>
            <p className="mt-3 inline-flex items-center gap-1 text-xs text-brand-300 opacity-0 transition group-hover:opacity-100">
              Choose variant <ArrowUpRight className="h-3 w-3" />
            </p>
          </button>
        ))}
      </div>
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
        {data.options.map((option) => (
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
