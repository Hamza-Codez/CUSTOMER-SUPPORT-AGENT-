/**
 * The brand, in one place.
 *
 * Every surface reads from here, so renaming the product is this file and
 * nothing else. It exists because the name is still being decided and a name
 * scattered across twelve components is a name nobody dares change.
 */

export const brand = {
  name: "Aperture",
  /** Used where the full name would wrap; keep it under ~10 characters. */
  short: "Aperture",
  /** The one-line pitch. Appears in the nav dropdown and og:description. */
  tagline: "The digital employee for your storefront",
  /** What it is, in a sentence someone could repeat. */
  promise:
    "It reads your real orders and your own written policies, settles what it can, and hands the rest to you as a decision worth one click.",
  domain: "aperture.support",
} as const;

/**
 * The product's own words. Kept out of components so the voice stays consistent
 * — the same idea phrased three different ways across three pages is how a
 * product starts sounding like a committee.
 */
export const voice = {
  grounded: "Grounded in your data, never the model's guesses",
  humanOwned: "Every decision that moves money is yours",
  notAChatbot: "Not a chatbot. An employee.",
} as const;
