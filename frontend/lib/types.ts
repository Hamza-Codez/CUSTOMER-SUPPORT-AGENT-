/** Mirrors the backend's Pydantic contracts in app/schemas/__init__.py. */

export type AgentAction = {
  kind: string;
  label: string;
  ref: string | null;
};

export type ChatResponse = {
  reply: string;
  session_id: string;
  actions: AgentAction[];
};

export type DecisionCard = {
  escalation_id: string;
  status: "pending" | "approved" | "declined";
  created_at: string;
  customer: {
    name?: string | null;
    verified?: boolean;
    via?: string | null;
    verified_orders?: string[];
  };
  request: string;
  policy_check: {
    result?: string;
    reason_codes?: string[];
    sources?: string[];
    order_status?: string | null;
    delivered_on?: string | null;
  };
  proposed_action: {
    type?: string;
    order_id?: string;
    amount?: string | null;
    method?: string;
  };
  options: string[];
  resolved_by: string | null;
  resolution_reason: string | null;
};

export type EscalationList = { escalations: DecisionCard[] };

export type DecisionResponse = {
  escalation_id: string;
  status: "approved" | "declined";
  outcome: string;
  customer_reply: string | null;
};

export type FeedbackSummary = {
  responses: number;
  average_rating: number | null;
  ratings: Record<string, number>;
};

export type Health = {
  status: "ok" | "degraded";
  provider: "mock" | "gemini";
  store: "mock" | "postgres";
  db: "up" | "down";
};

/** Chat transcript entry. `pending` drives the typing indicator. */
export type Message = {
  id: string;
  role: "user" | "agent";
  text: string;
  actions?: AgentAction[];
  pending?: boolean;
  failed?: boolean;
};
