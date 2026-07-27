import Link from "next/link";

import { brand } from "@/lib/brand";
import { cn } from "@/lib/utils";

/**
 * The mark.
 *
 * An aperture — overlapping blades opening onto a lit centre. It is the product
 * idea rather than decoration: the agent narrows the field until only what is
 * actually grounded gets through, and the human sits at the point of focus.
 *
 * Drawn rather than a letter in a box, which is what it was before and read as
 * exactly the placeholder it was.
 */
export function Mark({
  size = 28,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
      className={className}
    >
      <defs>
        <linearGradient id="ap-blade" x1="4" y1="2" x2="28" y2="30">
          <stop offset="0%" stopColor="var(--color-accent-soft)" />
          <stop offset="100%" stopColor="var(--color-accent-deep)" />
        </linearGradient>
        <radialGradient id="ap-core" cx="0.5" cy="0.45" r="0.6">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.95" />
          <stop offset="60%" stopColor="var(--color-accent-soft)" stopOpacity="0.9" />
          <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0.15" />
        </radialGradient>
      </defs>

      {/* Outer ring — the boundary the tools enforce. */}
      <circle
        cx="16"
        cy="16"
        r="13.25"
        stroke="url(#ap-blade)"
        strokeWidth="1.5"
        opacity="0.55"
      />

      {/* Three blades, 120° apart: the aperture stopped down to a point. */}
      {[0, 120, 240].map((angle) => (
        <path
          key={angle}
          d="M16 4.5 L26 14 L16 16 Z"
          fill="url(#ap-blade)"
          opacity="0.85"
          transform={`rotate(${angle} 16 16)`}
        />
      ))}

      {/* The lit centre — what actually gets through. */}
      <circle cx="16" cy="16" r="3.6" fill="url(#ap-core)" />
    </svg>
  );
}

/** Mark plus wordmark. `href` makes it a link; omit it inside a heading. */
export function Wordmark({
  href = "/",
  size = 28,
  className,
  showName = true,
}: {
  href?: string | null;
  size?: number;
  className?: string;
  showName?: boolean;
}) {
  const content = (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <Mark size={size} />
      {showName && (
        <span className="text-[15px] font-semibold tracking-[-0.02em] text-fg">
          {brand.name}
        </span>
      )}
    </span>
  );

  if (!href) return content;
  return (
    <Link href={href} className="group inline-flex items-center rounded-lg">
      {content}
    </Link>
  );
}
