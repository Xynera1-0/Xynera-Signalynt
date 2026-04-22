"use client";

import {
  ChannelSelector,
  PublishConfirmation,
  SignalMap,
  VariantComparisonGrid,
} from "./cards";

export default function EphemeralRenderer({ message, onAction }) {
  const data = message.ui_payload || {};

  switch (message.ui_type) {
    case "signal_map":
    case "research_brief":
      return <SignalMap data={data} />;

    case "variant_comparison":
    case "campaign_result":
    case "content_bundle":
      return (
        <VariantComparisonGrid
          data={data}
          onSelect={(variantName) =>
            onAction?.(`Selected creative: ${variantName}`)
          }
        />
      );

    case "channel_selector":
      return (
        <ChannelSelector
          data={data}
          onAction={(channel) => onAction?.(`Launch on ${channel}`)}
        />
      );

    case "publish_confirmation":
      return (
        <PublishConfirmation
          data={data}
          onConfirm={(campaignId, platforms) =>
            onAction?.(
              `Publish campaign ${campaignId} to ${(platforms || []).join(", ")}`,
            )
          }
        />
      );

    default:
      return (
        <div className="card">
          <p className="text-sm text-slate-300">
            {message.content || "Unsupported UI type."}
          </p>
        </div>
      );
  }
}
