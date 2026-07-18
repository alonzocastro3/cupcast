import Link from "next/link";
import type { MatchRead, TeamRead } from "@/lib/api";
import { formatDate, formatTime, formatStage, statusLabel, statusColor } from "@/lib/utils";

interface MatchCardProps {
  match: MatchRead;
  homeTeam?: TeamRead;
  awayTeam?: TeamRead;
}

export function MatchCard({ match, homeTeam, awayTeam }: MatchCardProps) {
  const isLive = match.status === "live";
  const isFinished = match.status === "finished";

  return (
    <Link
      href={`/matches/${match.id}`}
      className="group block rounded-xl border border-gray-800 bg-gray-900 p-5 transition-all duration-200 hover:border-emerald-500/50 hover:bg-gray-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
    >
      {/* Top row: stage + status */}
      <div className="mb-4 flex items-center justify-between">
        <span className="text-xs font-medium text-gray-500">
          {formatStage(match.stage)}
        </span>
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${statusColor(match.status)}`}
        >
          {isLive && (
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-red-500" />
            </span>
          )}
          {statusLabel(match.status)}
        </span>
      </div>

      {/* Teams + Score */}
      <div className="flex items-center gap-3">
        <div className="flex-1 text-right">
          <p className="text-sm font-bold text-white group-hover:text-emerald-400 transition-colors leading-tight">
            {homeTeam?.name ?? `Team #${match.home_team_id}`}
          </p>
          {homeTeam && (
            <p className="text-xs text-gray-500 mt-0.5">{homeTeam.country_code}</p>
          )}
        </div>

        <div className="flex-shrink-0 text-center min-w-[3rem]">
          {isFinished && match.home_score !== null && match.away_score !== null ? (
            <span className="text-lg font-bold text-white tabular-nums">
              {match.home_score}–{match.away_score}
            </span>
          ) : isLive && match.home_score !== null && match.away_score !== null ? (
            <span className="text-lg font-bold text-red-400 tabular-nums">
              {match.home_score}–{match.away_score}
            </span>
          ) : (
            <span className="text-sm font-semibold text-gray-500">vs</span>
          )}
        </div>

        <div className="flex-1 text-left">
          <p className="text-sm font-bold text-white group-hover:text-emerald-400 transition-colors leading-tight">
            {awayTeam?.name ?? `Team #${match.away_team_id}`}
          </p>
          {awayTeam && (
            <p className="text-xs text-gray-500 mt-0.5">{awayTeam.country_code}</p>
          )}
        </div>
      </div>

      {/* Kickoff */}
      <div className="mt-4 border-t border-gray-800 pt-3 flex items-center justify-between">
        <span className="text-xs text-gray-500">{formatDate(match.kickoff_at)}</span>
        <span className="text-xs text-gray-500">{formatTime(match.kickoff_at)}</span>
      </div>
    </Link>
  );
}
