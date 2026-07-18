"use client";

import { useState, useEffect } from "react";
import {
  api,
  ApiError,
  type PredictedOutcome,
  type PredictionSummary,
} from "@/lib/api";
import { getSessionId } from "@/lib/session";
import { formatOutcome } from "@/lib/utils";

interface Props {
  matchId: number;
  onSuccess: (summary: PredictionSummary) => void;
}

type FormState = "idle" | "loading" | "success" | "duplicate" | "error";

const OUTCOMES: { value: PredictedOutcome; label: string; color: string; active: string }[] = [
  {
    value: "home_win",
    label: "Home Win",
    color: "border-gray-700 text-gray-300 hover:border-emerald-500 hover:text-emerald-400",
    active: "border-emerald-500 bg-emerald-500/10 text-emerald-400",
  },
  {
    value: "draw",
    label: "Draw",
    color: "border-gray-700 text-gray-300 hover:border-amber-400 hover:text-amber-400",
    active: "border-amber-400 bg-amber-400/10 text-amber-400",
  },
  {
    value: "away_win",
    label: "Away Win",
    color: "border-gray-700 text-gray-300 hover:border-violet-500 hover:text-violet-400",
    active: "border-violet-500 bg-violet-500/10 text-violet-400",
  },
];

export function PredictionForm({ matchId, onSuccess }: Props) {
  const [outcome, setOutcome] = useState<PredictedOutcome | null>(null);
  const [homeScore, setHomeScore] = useState("");
  const [awayScore, setAwayScore] = useState("");
  const [formState, setFormState] = useState<FormState>("idle");
  const [scoreError, setScoreError] = useState<string | null>(null);
  const [successOutcome, setSuccessOutcome] = useState<PredictedOutcome | null>(null);

  // Check for existing submission on mount
  useEffect(() => {
    const stored = localStorage.getItem(`cupcast_submitted_${matchId}`);
    if (stored) setFormState("duplicate");
  }, [matchId]);

  function validateScores(): boolean {
    const hasHome = homeScore.trim() !== "";
    const hasAway = awayScore.trim() !== "";
    if (hasHome !== hasAway) {
      setScoreError("Enter both scores or leave both empty.");
      return false;
    }
    if (hasHome) {
      const h = parseInt(homeScore, 10);
      const a = parseInt(awayScore, 10);
      if (isNaN(h) || isNaN(a) || h < 0 || a < 0) {
        setScoreError("Scores must be non-negative integers.");
        return false;
      }
    }
    setScoreError(null);
    return true;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!outcome) return;
    if (!validateScores()) return;

    setFormState("loading");

    const sessionId = getSessionId();
    const hasScore = homeScore.trim() !== "" && awayScore.trim() !== "";

    try {
      const result = await api.matches.submitPrediction(matchId, {
        session_id: sessionId,
        predicted_outcome: outcome,
        predicted_home_score: hasScore ? parseInt(homeScore, 10) : null,
        predicted_away_score: hasScore ? parseInt(awayScore, 10) : null,
      });

      localStorage.setItem(`cupcast_submitted_${matchId}`, "1");
      setSuccessOutcome(outcome);
      setFormState("success");
      onSuccess(result.summary);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        localStorage.setItem(`cupcast_submitted_${matchId}`, "1");
        setFormState("duplicate");
      } else {
        setFormState("error");
      }
    }
  }

  if (formState === "success") {
    return (
      <div
        role="status"
        className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 px-4 py-5 text-center"
      >
        <p className="text-sm font-semibold text-emerald-400 mb-1">Prediction submitted!</p>
        {successOutcome && (
          <p className="text-xs text-gray-400">
            You picked <span className="text-white font-medium">{formatOutcome(successOutcome)}</span>
          </p>
        )}
      </div>
    );
  }

  if (formState === "duplicate") {
    return (
      <div
        role="status"
        className="rounded-xl border border-gray-700 bg-gray-800/40 px-4 py-5 text-center"
      >
        <p className="text-sm font-medium text-gray-400">You&apos;ve already predicted this match.</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate aria-label="Match prediction form">
      {/* Outcome buttons */}
      <fieldset>
        <legend className="text-xs text-gray-500 mb-3">Pick your outcome</legend>
        <div className="grid grid-cols-3 gap-2">
          {OUTCOMES.map(({ value, label, color, active }) => (
            <button
              key={value}
              type="button"
              aria-pressed={outcome === value}
              onClick={() => setOutcome(value)}
              className={`rounded-lg border py-2.5 text-xs font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 ${
                outcome === value ? active : color
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </fieldset>

      {/* Optional score */}
      <div className="mt-4">
        <p className="text-xs text-gray-500 mb-2">Predicted score (optional)</p>
        <div className="flex items-center gap-2">
          <label htmlFor="home-score" className="sr-only">
            Home score
          </label>
          <input
            id="home-score"
            type="number"
            min="0"
            value={homeScore}
            onChange={(e) => setHomeScore(e.target.value)}
            placeholder="0"
            aria-label="Home score"
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-center text-sm text-white placeholder-gray-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
          />
          <span className="text-gray-500 text-sm flex-shrink-0">–</span>
          <label htmlFor="away-score" className="sr-only">
            Away score
          </label>
          <input
            id="away-score"
            type="number"
            min="0"
            value={awayScore}
            onChange={(e) => setAwayScore(e.target.value)}
            placeholder="0"
            aria-label="Away score"
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-center text-sm text-white placeholder-gray-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
          />
        </div>
        {scoreError && (
          <p role="alert" className="mt-1.5 text-xs text-red-400">
            {scoreError}
          </p>
        )}
      </div>

      {/* Submit */}
      <button
        type="submit"
        disabled={!outcome || formState === "loading"}
        className="mt-4 w-full rounded-lg bg-emerald-500 py-2.5 text-sm font-semibold text-white transition-all hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
      >
        {formState === "loading" ? "Submitting…" : "Submit Prediction"}
      </button>

      {formState === "error" && (
        <p role="alert" className="mt-2 text-center text-xs text-red-400">
          Something went wrong. Please try again.
        </p>
      )}
    </form>
  );
}
