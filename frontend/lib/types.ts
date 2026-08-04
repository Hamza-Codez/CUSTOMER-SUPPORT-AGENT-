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

export type OrderSummary = {
  order_id: string;
  customer_name: string;
  status: string;
  placed_at: string;
  eta: string | null;
  item_count: number;
  total: string;
};

export type ProductSummary = {
  product_id: string;
  name: string;
  price: string;
  stock: number;
  in_stock: boolean;
  summary: string;
};

export type PolicySummary = {
  doc: string;
  topic: string;
  source_ref: string;
};

export type ActivityEntry = {
  actor: string;
  action: string;
  target: string;
  outcome: string;
  ts: string;
};

export type Overview = {
  orders: OrderSummary[];
  products: ProductSummary[];
  policies: PolicySummary[];
  recent_activity: ActivityEntry[];
  counts: Record<string, number>;
};

export type EmailPreview = {
  subject: string;
  body_html: string;
  recipient: string;
  status: string;
  feedback_token: string;
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

export type Analytics = {
  conversations: number;
  escalated_conversations: number;
  deflection_rate: number | null;
  escalations: Record<string, number>;
  handoff_approval_rate: number | null;
  csat_responses: number;
  csat_average: number | null;
  refunds_executed: number;
  model_requests: number;
  total_tokens: number;
  tokens_per_conversation: number | null;
  cost_per_conversation: number | null;
  cost_note: string | null;
};

export type IntegrationRequestBody = {
  contact_name: string;
  contact_email: string;
  website?: string;
  platform?: string;
  monthly_conversations?: string;
  notes?: string;
};

export type IntegrationAccepted = {
  request_id: string;
  status: string;
  message: string;
};

export type SiteKey = {
  key: string;
  label: string;
  allowed_origins: string[];
  preview: boolean;
  active: boolean;
  created_at: string;
  revoked_at: string | null;
  /** Assembled server-side, so a copied snippet can never disagree with itself. */
  snippet: string;
};

export type SiteKeyList = { keys: SiteKey[] };

export type ScannedPage = {
  url: string;
  title: string;
  topic: string;
  text: string;
  /** Why this page was picked — shown so the seller can see we didn't guess. */
  matched: string;
};

export type SiteScanResult = {
  site: string;
  pages: ScannedPage[];
  /** [url, reason] for pages we tried and couldn't use. */
  skipped: string[][];
  note: string;
};

export type Account = {
  user_id: string;
  username: string;
  business_id: string;
  business_name: string;
  email: string;
  name: string;
  role: string;
  profile_completed?: boolean;
};

export type AuthResponse = {
  token: string;
  expires_in_days: number;
  account: Account;
};
