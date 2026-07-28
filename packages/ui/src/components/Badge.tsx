import type { ReactNode } from "react";
import type { BadgeVariant } from "../types.js";

interface BadgeProps {
  variant?: BadgeVariant;
  children: ReactNode;
  className?: string;
}

const BADGE_CLASSES: Record<BadgeVariant, string> = {
  gray: "bg-gray-100 text-gray-700",
  blue: "bg-blue-100 text-blue-700",
  green: "bg-green-100 text-green-700",
  yellow: "bg-yellow-100 text-yellow-800",
  red: "bg-red-100 text-red-700",
  purple: "bg-purple-100 text-purple-700",
};

export function Badge({ variant = "gray", children, className = "" }: BadgeProps): JSX.Element {
  return (
    <span
      className={["inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium", BADGE_CLASSES[variant], className].join(" ")}
    >
      {children}
    </span>
  );
}
