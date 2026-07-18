import type { ModelPrediction } from "@/lib/api";
import { formatPct } from "@/lib/utils";

interface ProbabilityBarProps {
  prediction: ModelPrediction;
  compact?: boolean;
}

export function ProbabilityBar({ prediction, compact = false }: ProbabilityBarProps) {
  const { home_team, away_team, home_win_probability, draw_probability, away_win_probability } =
    prediction;

  const homePct = home_win_probability * 100;
  const drawPct = draw_probability * 100;
  const awayPct = away_win_probability * 100;

  return (
    <div className="space-y-2">
      {!compact && (
        <div className="flex justify-between text-xs text-gray-400 font-medium">
          <span>{home_team.name}</span>
          <span>Draw</span>
          <span>{away_team.name}</span>
        </div>
      )}

      {/* Bar */}
      <div
        className="flex h-3 w-full overflow-hidden rounded-full bg-gray-800"
        role="img"
        aria-label={`Home win ${formatPct(homePct)}, Draw ${formatPct(drawPct)}, Away win ${formatPct(awayPct)}`}
      >
        <div
          className="bg-emerald-500 transition-all"
          style={{ width: `${homePct}%` }}
        />
        <div
          className="bg-amber-400 transition-all"
          style={{ width: `${drawPct}%` }}
        />
        <div
          className="bg-violet-500 transition-all"
          style={{ width: `${awayPct}%` }}
        />
      </div>

      {/* Labels */}
      <div className="flex justify-between text-xs font-mono">
        <span className="text-emerald-400">{formatPct(homePct)}</span>
        <span className="text-amber-400">{formatPct(drawPct)}</span>
        <span className="text-violet-400">{formatPct(awayPct)}</span>
      </div>
    </div>
  );
}
