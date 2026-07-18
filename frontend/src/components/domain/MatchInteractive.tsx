"use client";

import { useState } from "react";
import type { PredictionSummary } from "@/lib/api";
import { PredictionForm } from "./PredictionForm";
import { EmptyState } from "@/components/ui/EmptyState";

interface Props {
  matchId: number;
  initialSummary: PredictionSummary | null;
}

export function MatchInteractive({ matchId, initialSummary }: Props) {
  const [summary, setSummary] = useState<PredictionSummary | null>(initialSummary);

  return (
    <>
      {/* Community Predictions */}
      <div className="rounded-2xl border border-gray-800 bg-gray-900 p-6">
        <h2 className="text-base font-bold text-white mb-5">Community Predictions</h2>

        {!summary || summary.total_predictions === 0 ? (
          <EmptyState
            title="No community predictions yet"
            message="Be the first to predict the outcome of this match."
            icon="🗳️"
          />
        ) : (
          <div>
            <p className="text-xs text-gray-500 mb-4">
              Based on {summary.total_predictions} prediction
              {summary.total_predictions !== 1 ? "s" : ""}
            </p>
            <div className="space-y-3">
              {[
                {
                  label: "Home Win",
                  count: summary.home_win_count,
                  pct: summary.home_win_percentage,
                  color: "bg-emerald-500",
                  text: "text-emerald-400",
                },
                {
                  label: "Draw",
                  count: summary.draw_count,
                  pct: summary.draw_percentage,
                  color: "bg-amber-400",
                  text: "text-amber-400",
                },
                {
                  label: "Away Win",
                  count: summary.away_win_count,
                  pct: summary.away_win_percentage,
                  color: "bg-violet-500",
                  text: "text-violet-400",
                },
              ].map(({ label, count, pct, color, text }) => (
                <div key={label}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-gray-300">{label}</span>
                    <span className={`text-sm font-semibold ${text}`}>
                      {pct.toFixed(1)}%{" "}
                      <span className="text-gray-500 font-normal text-xs">({count})</span>
                    </span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-gray-800">
                    <div
                      className={`h-full rounded-full ${color} transition-all`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Prediction Form */}
      <div className="rounded-2xl border border-gray-800 bg-gray-900 p-6">
        <h2 className="text-base font-bold text-white mb-5">Your Prediction</h2>
        <PredictionForm matchId={matchId} onSuccess={setSummary} />
      </div>
    </>
  );
}
