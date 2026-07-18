import Link from "next/link";
import type { TeamRead } from "@/lib/api";
import { formatStage } from "@/lib/utils";

interface TeamCardProps {
  team: TeamRead;
}

export function TeamCard({ team }: TeamCardProps) {
  const totalGames = team.wins + team.draws + team.losses;
  const totalGoals = team.goals_for + team.goals_against;

  return (
    <Link
      href={`/teams/${team.id}`}
      className="group block rounded-xl border border-gray-800 bg-gray-900 p-5 transition-all duration-200 hover:border-emerald-500/50 hover:bg-gray-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-base font-bold text-white group-hover:text-emerald-400 transition-colors">
            {team.name}
          </h3>
          <p className="text-sm text-gray-400 mt-0.5">
            {formatStage(team.group_name)}
          </p>
        </div>
        <div className="flex-shrink-0 rounded-md bg-gray-800 border border-gray-700 px-2.5 py-1 text-xs font-bold tracking-widest text-gray-300 group-hover:border-emerald-500/30 transition-colors">
          {team.country_code}
        </div>
      </div>

      {/* Rankings */}
      <div className="mb-4 grid grid-cols-2 gap-3">
        <div className="rounded-lg bg-gray-800/60 px-3 py-2">
          <p className="text-xs text-gray-500 mb-0.5">FIFA Rank</p>
          <p className="text-sm font-semibold text-white">#{team.fifa_ranking}</p>
        </div>
        <div className="rounded-lg bg-gray-800/60 px-3 py-2">
          <p className="text-xs text-gray-500 mb-0.5">Elo Rating</p>
          <p className="text-sm font-semibold text-white">{team.elo_rating}</p>
        </div>
      </div>

      {/* Record */}
      {totalGames > 0 && (
        <div className="flex items-center justify-between text-xs border-t border-gray-800 pt-3">
          <span className="text-emerald-400 font-semibold">{team.wins}W</span>
          <span className="text-amber-400 font-semibold">{team.draws}D</span>
          <span className="text-red-400 font-semibold">{team.losses}L</span>
          {totalGoals > 0 && (
            <span className="text-gray-400">
              {team.goals_for}–{team.goals_against}
            </span>
          )}
        </div>
      )}
    </Link>
  );
}
