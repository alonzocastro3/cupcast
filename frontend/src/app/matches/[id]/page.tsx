import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { api, ApiError, type ModelPrediction, type PredictionSummary } from "@/lib/api";
import { ProbabilityBar } from "@/components/domain/ProbabilityBar";
import { PredictionBadge } from "@/components/domain/PredictionBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { MatchInteractive } from "@/components/domain/MatchInteractive";
import { formatDateTime, formatStage, statusLabel, statusColor, confidenceLabel } from "@/lib/utils";

interface Props {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  try {
    const pred = await api.matches.modelPrediction(Number(id));
    return {
      title: `${pred.home_team.name} vs ${pred.away_team.name}`,
      description: `Model pick: ${pred.predicted_outcome.replace("_", " ")} · confidence ${(pred.confidence * 100).toFixed(0)}%`,
    };
  } catch {
    return { title: "Match" };
  }
}

export const dynamic = "force-dynamic";

export default async function MatchPage({ params }: Props) {
  const { id } = await params;
  const matchId = Number(id);

  let prediction: ModelPrediction | null = null;
  let summary: PredictionSummary | null = null;

  // Model prediction includes team data — use it as the primary source
  try {
    prediction = await api.matches.modelPrediction(matchId);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    // Non-fatal — render without prediction
  }

  // If prediction failed but match might still exist, try the base match endpoint
  if (!prediction) {
    try {
      await api.matches.get(matchId);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) notFound();
    }
  }

  try {
    summary = await api.matches.predictionSummary(matchId);
  } catch {
    // Non-fatal
  }

  // Fetch the real match for status/kickoff
  let matchDetail: Awaited<ReturnType<typeof api.matches.get>> | null = null;
  try {
    matchDetail = await api.matches.get(matchId);
  } catch {
    // Non-fatal
  }

  const homeTeam = prediction?.home_team;
  const awayTeam = prediction?.away_team;

  const isLive = matchDetail?.status === "live";
  const isFinished = matchDetail?.status === "finished";

  return (
    <div className="mx-auto max-w-3xl px-4 sm:px-6 py-10">
      {/* Back */}
      <Link
        href="/matches"
        className="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-white mb-8 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 rounded-sm"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        All Matches
      </Link>

      {/* Match header */}
      <div className="rounded-2xl border border-gray-800 bg-gray-900 p-6 sm:p-8 mb-6">
        {/* Stage + status */}
        <div className="flex items-center justify-between mb-6">
          <span className="text-xs font-medium text-gray-500 uppercase tracking-widest">
            {matchDetail ? formatStage(matchDetail.stage) : "Match"}
          </span>
          {matchDetail && (
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium ${statusColor(matchDetail.status)}`}
            >
              {isLive && (
                <span className="relative flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-red-500" />
                </span>
              )}
              {statusLabel(matchDetail.status)}
            </span>
          )}
        </div>

        {/* Teams */}
        <div className="flex items-center justify-center gap-4 sm:gap-8 mb-6">
          <div className="text-center flex-1">
            {homeTeam ? (
              <Link
                href={`/teams/${homeTeam.id}`}
                className="group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 rounded-sm"
              >
                <p className="text-xl sm:text-2xl font-extrabold text-white group-hover:text-emerald-400 transition-colors">
                  {homeTeam.name}
                </p>
                <p className="text-xs text-gray-500 mt-1">{homeTeam.country_code}</p>
              </Link>
            ) : (
              <p className="text-xl font-bold text-gray-400">—</p>
            )}
          </div>

          <div className="flex-shrink-0 text-center">
            {isFinished &&
            matchDetail != null &&
            matchDetail.home_score !== null &&
            matchDetail.away_score !== null ? (
              <div className="text-center">
                <span className="text-4xl font-extrabold text-white tabular-nums">
                  {matchDetail.home_score}–{matchDetail.away_score}
                </span>
                <p className="text-xs text-gray-500 mt-1">Final</p>
              </div>
            ) : isLive &&
              matchDetail != null &&
              matchDetail.home_score !== null &&
              matchDetail.away_score !== null ? (
              <div>
                <span className="text-4xl font-extrabold text-red-400 tabular-nums">
                  {matchDetail.home_score}–{matchDetail.away_score}
                </span>
                <p className="text-xs text-red-400 mt-1 font-medium">Live</p>
              </div>
            ) : (
              <div>
                <span className="text-2xl font-bold text-gray-600">vs</span>
                {matchDetail && (
                  <p className="text-xs text-gray-500 mt-2 whitespace-nowrap">
                    {formatDateTime(matchDetail.kickoff_at)}
                  </p>
                )}
              </div>
            )}
          </div>

          <div className="text-center flex-1">
            {awayTeam ? (
              <Link
                href={`/teams/${awayTeam.id}`}
                className="group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 rounded-sm"
              >
                <p className="text-xl sm:text-2xl font-extrabold text-white group-hover:text-emerald-400 transition-colors">
                  {awayTeam.name}
                </p>
                <p className="text-xs text-gray-500 mt-1">{awayTeam.country_code}</p>
              </Link>
            ) : (
              <p className="text-xl font-bold text-gray-400">—</p>
            )}
          </div>
        </div>

        {matchDetail?.venue && (
          <p className="text-center text-xs text-gray-500">{matchDetail.venue}</p>
        )}
      </div>

      {/* Model Prediction */}
      {prediction ? (
        <div className="rounded-2xl border border-gray-800 bg-gray-900 p-6 mb-6">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-base font-bold text-white">Model Prediction</h2>
              <p className="text-xs text-gray-500 mt-0.5">v{prediction.model_version}</p>
            </div>
            <div className="text-right">
              <PredictionBadge outcome={prediction.predicted_outcome} />
              <p className="text-xs text-gray-500 mt-1">
                {confidenceLabel(prediction.confidence)} ·{" "}
                {(prediction.confidence * 100).toFixed(0)}%
              </p>
            </div>
          </div>

          <ProbabilityBar prediction={prediction} />

          {prediction.explanation && (
            <div className="mt-5 rounded-lg bg-gray-800/50 border border-gray-700/50 px-4 py-3">
              <p className="text-xs text-gray-300 leading-relaxed">{prediction.explanation}</p>
            </div>
          )}
        </div>
      ) : (
        <div className="rounded-2xl border border-gray-800 bg-gray-900 p-6 mb-6">
          <EmptyState
            title="Prediction unavailable"
            message="The model prediction could not be loaded for this match."
            icon="🔮"
          />
        </div>
      )}

      {/* Community Predictions + Prediction Form (client component for interactivity) */}
      <MatchInteractive matchId={matchId} initialSummary={summary} />

      {/* Team comparison */}
      {homeTeam && awayTeam && (
        <div className="mt-6 rounded-2xl border border-gray-800 bg-gray-900 p-6">
          <h2 className="text-base font-bold text-white mb-5">Team Comparison</h2>
          <div className="space-y-4">
            {[
              {
                label: "FIFA Ranking",
                home: `#${homeTeam.fifa_ranking}`,
                away: `#${awayTeam.fifa_ranking}`,
                homeBetter: homeTeam.fifa_ranking < awayTeam.fifa_ranking,
              },
              {
                label: "Elo Rating",
                home: homeTeam.elo_rating.toLocaleString(),
                away: awayTeam.elo_rating.toLocaleString(),
                homeBetter: homeTeam.elo_rating > awayTeam.elo_rating,
              },
              {
                label: "Recent Form",
                home: homeTeam.recent_form_score.toFixed(2),
                away: awayTeam.recent_form_score.toFixed(2),
                homeBetter: homeTeam.recent_form_score > awayTeam.recent_form_score,
              },
              {
                label: "Goals For",
                home: String(homeTeam.goals_for),
                away: String(awayTeam.goals_for),
                homeBetter: homeTeam.goals_for > awayTeam.goals_for,
              },
            ].map(({ label, home, away, homeBetter }) => (
              <div key={label} className="grid grid-cols-3 items-center gap-4 text-sm">
                <span
                  className={`text-right font-semibold ${homeBetter ? "text-emerald-400" : "text-gray-300"}`}
                >
                  {home}
                </span>
                <span className="text-center text-xs text-gray-500">{label}</span>
                <span
                  className={`text-left font-semibold ${!homeBetter ? "text-emerald-400" : "text-gray-300"}`}
                >
                  {away}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
