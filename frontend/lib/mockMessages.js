export const initialMessages = [
  {
    id: "m1",
    role: "agent",
    title: "Morning signal snapshot",
    ui_type: "signal_map",
    ui_payload: {
      territory: "US Medicaid",
      signals: [
        { label: "Policy chatter", value: 87, trend: "+11%" },
        { label: "Competitor launches", value: 62, trend: "+4%" },
        { label: "Audience urgency", value: 79, trend: "+8%" },
      ],
    },
  },
  {
    id: "m2",
    role: "agent",
    title: "Variant recommendation",
    ui_type: "variant_comparison",
    ui_payload: {
      variants: [
        { name: "Insight-led", ctr: 3.9, cvr: 1.7, sentiment: "high trust" },
        { name: "ROI-led", ctr: 4.4, cvr: 1.4, sentiment: "curious" },
        { name: "Urgency-led", ctr: 5.1, cvr: 1.1, sentiment: "mixed" },
      ],
    },
  },
  {
    id: "m3",
    role: "agent",
    title: "Push to action",
    ui_type: "channel_selector",
    ui_payload: {
      options: ["LinkedIn", "Email", "Webinar"],
      prompt: "Where should we launch the winning creative first?",
    },
  },
];
