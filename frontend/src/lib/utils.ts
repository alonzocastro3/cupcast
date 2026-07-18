import type { MatchStatus, PredictedOutcome } from "./api";

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDateTime(iso: string): string {
  return `${formatDate(iso)} · ${formatTime(iso)}`;
}

export function formatStage(stage: string): string {
  return stage
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function formatOutcome(outcome: PredictedOutcome): string {
  const map: Record<PredictedOutcome, string> = {
    home_win: "Home Win",
    away_win: "Away Win",
    draw: "Draw",
  };
  return map[outcome];
}

export function formatPct(n: number): string {
  return `${n.toFixed(1)}%`;
}

export function statusLabel(status: MatchStatus): string {
  const map: Record<MatchStatus, string> = {
    scheduled: "Upcoming",
    live: "Live",
    finished: "Final",
    cancelled: "Cancelled",
  };
  return map[status];
}

export function statusColor(status: MatchStatus): string {
  const map: Record<MatchStatus, string> = {
    scheduled: "text-sky-400 bg-sky-400/10 border-sky-400/30",
    live: "text-red-400 bg-red-400/10 border-red-400/30",
    finished: "text-gray-400 bg-gray-400/10 border-gray-400/30",
    cancelled: "text-orange-400 bg-orange-400/10 border-orange-400/30",
  };
  return map[status];
}

export function confidenceLabel(score: number): string {
  if (score >= 0.6) return "High confidence";
  if (score >= 0.35) return "Moderate confidence";
  return "Low confidence";
}
