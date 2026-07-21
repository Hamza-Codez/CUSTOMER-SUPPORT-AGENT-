import { cn } from "@/lib/utils";

export function Card({ className, ...props }) {
  return (
    <div
      className={cn("rounded-2xl border border-base-line bg-base-800 shadow-card", className)}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }) {
  return <div className={cn("flex items-start justify-between gap-3 p-4 pb-0", className)} {...props} />;
}

export function CardBody({ className, ...props }) {
  return <div className={cn("p-4", className)} {...props} />;
}
