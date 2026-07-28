import { Badge } from "./Badge.js";
import type { BadgeVariant } from "../types.js";

// This matches ApplicationStatus from @career-pilot/contracts
type ApplicationStatus =
  | "draft"
  | "matched"
  | "packet_draft"
  | "packet_ready"
  | "human_review"
  | "approved"
  | "stopped_before_submit"
  | "submitted";

const STATUS_CONFIG: Record<ApplicationStatus, { label: string; variant: BadgeVariant }> = {
  draft: { label: "Draft", variant: "gray" },
  matched: { label: "Matched", variant: "blue" },
  packet_draft: { label: "Packet Draft", variant: "blue" },
  packet_ready: { label: "Packet Ready", variant: "purple" },
  human_review: { label: "Human Review", variant: "yellow" },
  approved: { label: "Approved", variant: "green" },
  stopped_before_submit: { label: "Pending Authorization", variant: "yellow" },
  submitted: { label: "Submitted", variant: "green" },
};

interface StatusBadgeProps {
  status: ApplicationStatus;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps): JSX.Element {
  const config = STATUS_CONFIG[status] ?? { label: status, variant: "gray" as BadgeVariant };
  const props = { variant: config.variant, children: config.label } as const;
  return className === undefined ? <Badge {...props} /> : <Badge {...props} className={className} />;
}
