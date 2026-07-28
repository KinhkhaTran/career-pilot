import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  padding?: "none" | "sm" | "md" | "lg";
}

interface CardHeaderProps {
  title: string;
  description?: string;
  action?: ReactNode;
}

const PADDING_CLASSES: Record<"none" | "sm" | "md" | "lg", string> = {
  none: "",
  sm: "p-4",
  md: "p-6",
  lg: "p-8",
};

export function Card({ children, className = "", padding = "md" }: CardProps): JSX.Element {
  return (
    <div
      className={["bg-white rounded-lg border border-gray-200 shadow-sm", PADDING_CLASSES[padding], className].join(" ")}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, description, action }: CardHeaderProps): JSX.Element {
  return (
    <div className="flex items-start justify-between mb-4">
      <div>
        <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
        {description ? <p className="mt-1 text-sm text-gray-500">{description}</p> : null}
      </div>
      {action ? <div className="ml-4 flex-shrink-0">{action}</div> : null}
    </div>
  );
}
