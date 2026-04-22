"use client";

import {
  ChannelSelector,
  ContentCard,
  FlyerCard,
  PublishConfirmation,
  SignalMap,
  VariantComparisonGrid,
} from "./cards";

export default function EphemeralRenderer({ message, onAction, onExpand }) {
  const data = message.ui_payload || {};

  switch (message.ui_type) {
    case "flyer":
      return <FlyerCard data={data} onExpand={onExpand} />;

    case "signal_map":
    case "research_brief":
      return <SignalMap data={data} />;

    case "variant_comparison":
    case "campaign_result":
    case "content_bundle":
      // If the payload has a typed result from the agent, use the rich ContentCard
      if (data.result?.content_type && data.result.content_type !== "flyer") {
        return <ContentCard data={data} />;
      }
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
