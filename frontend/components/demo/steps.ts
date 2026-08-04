/**
 * The guided tour, per SPEC §15.
 *
 * Each step is a card with one clear thing to do. Nothing advances on a timer:
 * the visitor drives, so they can read, or skip ahead, or sit on the Decision
 * Card for a minute before approving.
 *
 * Every action here is a real message to the real agent against the seed
 * database. Scripting the replies would make a smoother demo and prove nothing,
 * which is the opposite of the point.
 */

export type Side = "customer" | "seller";

export type Step = {
  id: string;
  side: Side;
  title: string;
  body: string;
  /** The one-line reason this step exists — the "aha" from the spec's table. */
  aha: string;
  /** A chat message the step sends for them, if any. */
  send?: string;
  /** Label on the button that performs the step. */
  action: string;
  /** Shown when the step is complete, before they move on. */
  done?: string;
  /** Which tools to light up green when this step is performed (useful for frontend-only mode). */
  tools?: import("../../lib/tools").ToolId[];
};

export const STEPS: Step[] = [
  {
    id: "meet",
    side: "customer",
    title: "Meet your new employee",
    body: "This is the support surface your customers see. The chips below the box are one-tap starters, so nobody faces a blank prompt.",
    aha: "Guided, not a blank box",
    action: "Say hello",
    send: "Hi — what can you help me with?",
    done: "It offered what it can actually do, rather than promising everything.",
    tools: ["route"],
  },
  {
    id: "identity",
    side: "customer",
    title: "It checks who it is talking to",
    body: "Ask where an order is without proving anything. It will not reveal a single detail until the order number and the email on it match.",
    aha: "Careful, not reckless",
    action: "Ask without verifying",
    send: "Where is my order ORD-1002?",
    done: "No status, no carrier, no tracking — it asked for the email first.",
    tools: ["order_lookup"],
  },
  {
    id: "lookup",
    side: "customer",
    title: "Now with the details",
    body: "Give it the order number and the matching email. What comes back is read live from the database — carrier, tracking number and ETA are real rows, not sample text.",
    aha: "Real data, not canned text",
    action: "Verify and look up",
    send: "It's ORD-1002, and my email is ayesha.k@example.com",
    done: "The chip under the reply is proof a tool ran. It cannot appear otherwise.",
    tools: ["order_lookup"],
  },
  {
    id: "products",
    side: "customer",
    title: "Support quietly becomes sales",
    body: "Ask it to compare two desks. It answers from the catalogue — real prices, real stock — and will tell you plainly when something is out of stock.",
    aha: "It sells as well as serves",
    action: "Compare two products",
    send: "Which is better, the AeroDesk Pro or the AeroDesk Lite?",
    done: "Both products came from the catalogue, with the differences that matter.",
    tools: ["product_catalog"],
  },
  {
    id: "refund-ok",
    side: "customer",
    title: "A refund it can settle itself",
    body: "ORD-1005 is small, recent and inside the refund window. Watch it check the policy, verify identity, and complete the refund without asking anyone.",
    aha: "Grounded, polite, policy-driven",
    action: "Request a small refund",
    send: "I'd like a refund for ORD-1005, my email is ayesha.k@example.com",
    done: "Refunded on the spot — under the cap and inside the window.",
    tools: ["policy_retriever", "refund_processor"],
  },
  {
    id: "refund-human",
    side: "customer",
    title: "And one it will not",
    body: "ORD-1001 is £149 — above the automatic limit. The same request, a different answer: it prepares everything and stops.",
    aha: "It knows its limits",
    action: "Request a larger refund",
    send: "Actually I also want a refund for ORD-1001, same email ayesha.k@example.com",
    done: "No money moved. It has been handed to a person — let's go and be that person.",
    tools: ["refund_processor", "human_escalation"],
  },
  {
    id: "decision",
    side: "seller",
    title: "The other side of the same window",
    body: "This is what your operator sees. The card carries the verified customer, the request, why it stopped, and the proposed action. Everything on it was produced by a tool, never asserted by the model — which is what makes one click safe.",
    aha: "The ready-to-click-OK moment",
    action: "Approve the refund",
    done: "Approving resumed the original paused run — not a new one.",
  },
  {
    id: "loop",
    side: "customer",
    title: "It closes the loop",
    body: "The outcome went back into the same conversation the customer was already in. Ask for it in writing and you will get the themed summary and a one-tap rating.",
    aha: "Seamless, end to end",
    action: "Ask for it in writing",
    send: "Great — can you email me a summary?",
    done: "That is the real message, rendered exactly as it was stored.",
    tools: ["send_summary_email"],
  },
  {
    id: "ops",
    side: "seller",
    title: "It is an operator, not a toy",
    body: "Your records, your stock, your policy documents, and every sensitive thing the agent did — including the times it refused.",
    aha: "A real operations surface",
    action: "Open the operations view",
    done: "Every refusal is logged too. Those are usually the interesting ones.",
  },
  {
    id: "convert",
    side: "customer",
    title: "That was your FTE on sample data",
    body: "Everything you just watched ran against a seeded store. Point it at your own catalogue, your own policies and your own orders, and it behaves the same way.",
    aha: "Ready for your store",
    action: "See pricing",
  },
];
