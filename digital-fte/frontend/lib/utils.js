import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge conditional classes without Tailwind conflicts. */
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
