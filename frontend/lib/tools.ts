/**
 * The agent's tools, as the interface presents them.
 *
 * One mapping so the action chips under a reply and the tool rack beside it can
 * never disagree about what just ran. `kinds` are the `AgentAction.kind` values
 * the backend emits — a tool lights up only because the backend said it acted.
 */

export type ToolId =
  | "route"
  | "order_lookup"
  | "policy_retriever"
  | "product_catalog"
  | "refund_processor"
  | "human_escalation"
  | "send_summary_email";

export type ToolSpec = {
  id: ToolId;
  name: string;
  /** What it does, for the rack's tooltip and the landing page. */
  blurb: string;
  /** Action kinds the backend emits when this tool acted. */
  kinds: string[];
  /** True for tools that can move money or leave the building. */
  gated?: boolean;
};

export const TOOLS: ToolSpec[] = [
  {
    id: "route",
    name: "Triage",
    blurb: "Reads what the customer wants and hands it to the right specialist.",
    kinds: ["routed"],
  },
  {
    id: "order_lookup",
    name: "Order lookup",
    blurb:
      "Reads a real order, but only after the order number and the email on it match.",
    kinds: ["order_looked_up", "order_not_found", "identity_check_failed"],
  },
  {
    id: "policy_retriever",
    name: "Policy retrieval",
    blurb:
      "Finds the passage in your own documents, and returns nothing when there isn't one.",
    kinds: ["policy_cited", "no_policy_match"],
  },
  {
    id: "product_catalog",
    name: "Catalogue",
    blurb: "Real prices and real stock. Never a product from memory.",
    kinds: ["product_viewed", "products_compared", "no_product_match"],
  },
  {
    id: "refund_processor",
    name: "Refunds",
    blurb:
      "Settles small, recent, in-policy refunds. Everything else waits for you.",
    kinds: [
      "refund_executed",
      "refund_duplicate",
      "refund_refused",
      "approval_pending",
    ],
    gated: true,
  },
  {
    id: "human_escalation",
    name: "Escalation",
    blurb: "Hands the conversation to a person with the decision already prepared.",
    kinds: ["escalated"],
    gated: true,
  },
  {
    id: "send_summary_email",
    name: "Summary email",
    blurb:
      "Emails a recap and a one-tap rating — only ever to the verified address.",
    kinds: ["email_sent", "email_already_sent", "email_refused", "email_failed"],
    gated: true,
  },
];

const BY_KIND = new Map<string, ToolSpec>();
for (const tool of TOOLS) {
  for (const kind of tool.kinds) BY_KIND.set(kind, tool);
}

export function toolForKind(kind: string): ToolSpec | undefined {
  return BY_KIND.get(kind);
}

/** How a given outcome went, for colouring. Refusals are not failures. */
export type Verdict = "ok" | "held" | "blocked" | "neutral";

const VERDICTS: Record<string, Verdict> = {
  routed: "neutral",
  order_looked_up: "ok",
  order_not_found: "held",
  identity_check_failed: "blocked",
  policy_cited: "ok",
  no_policy_match: "held",
  product_viewed: "ok",
  products_compared: "ok",
  no_product_match: "held",
  refund_executed: "ok",
  refund_duplicate: "neutral",
  refund_refused: "blocked",
  approval_pending: "held",
  escalated: "held",
  email_sent: "ok",
  email_already_sent: "neutral",
  email_refused: "held",
  email_failed: "blocked",
  blocked: "blocked",
  ungrounded_blocked: "held",
  agent_stuck: "held",
};

export function verdictFor(kind: string): Verdict {
  return VERDICTS[kind] ?? "neutral";
}
