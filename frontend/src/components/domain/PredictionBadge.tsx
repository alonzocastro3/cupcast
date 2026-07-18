import type { PredictedOutcome } from "@/lib/api";
import { formatOutcome } from "@/lib/utils";

interface PredictionBadgeProps {
  outcome: PredictedOutcome;
  size?: "sm" | "md";
}

const styles: Record<PredictedOutcome, string> = {
  home_win: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  away_win: "bg-violet-500/15 text-violet-400 border-violet-500/30",
  draw: "bg-amber-500/15 text-amber-400 border-amber-500/30",
};

export function PredictionBadge({ outcome, size = "md" }: PredictionBadgeProps) {
  const sizeClass = size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm";
  return (
    <span
      className={`inline-flex items-center rounded-full border font-medium ${sizeClass} ${styles[outcome]}`}
    >
      {formatOutcome(outcome)}
    </span>
  );
}
