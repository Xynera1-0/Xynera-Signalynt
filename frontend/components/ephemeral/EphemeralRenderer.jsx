"use client";

import { ChannelSelector, SignalMap, VariantComparisonGrid } from "./cards";

export default function EphemeralRenderer({ message, onAction }) {
  switch (message.ui_type) {
    case "signal_map":
      return <SignalMap data={message.ui_payload} />;
    case "variant_comparison":
      return (
        <VariantComparisonGrid
          data={message.ui_payload}
          onSelect={(variantName) => onAction(`Selected creative: ${variantName}`)}
        />
      );
    case "channel_selector":
      return <ChannelSelector data={message.ui_payload} onAction={(channel) => onAction(`Launch on ${channel}`)} />;
    default:
      return (
        <div className="card">
          <p className="text-sm text-slate-300">{message.content || "Unsupported UI type."}</p>
        </div>
      );
  }
}
