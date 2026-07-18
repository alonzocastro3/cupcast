import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { api, ApiError, type TeamRead, type MatchRead } from "@/lib/api";
import { MatchCard } from "@/components/domain/MatchCard";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatStage } from "@/lib/utils";

interface Props {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  try {
    const team = await api.teams.get(Number(id));
    return {
      title: team.name,
      description: `FIFA ranking #${team.fifa_ranking} · Elo ${team.elo_rating} · ${team.group_name}`,
    };
  } catch {
    return { title: "Team not found" };
  }
}

export const dynamic = "force-dynamic";

export default async function TeamPage({ params }: Props) {
  const { id } = await params;
  const teamId = Number(id);

  let team: TeamRead;
  let matches: MatchRead[] = [];
  let teamMap = new Map<number, TeamRead>();

  try {
    team = await api.teams.get(teamId);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  try {
    const [matchesPage, allTeamsPage] = await Promise.all([
      api.matches.list({ team_id: teamId, limit: 100 }),
      api.teams.list({ limit: 100 }),
    ]);
    matches = matchesPage.items;
    teamMap = new Map(allTeamsPage.items.map((t) => [t.id, t]));
  } catch {
    // Non-fatal — show team without matches
  }

  const totalGames = team.wins + team.draws + team.losses;
  const winRate = totalGames > 0 ? ((team.wins / totalGames) * 100).toFixed(0) : null;

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 py-10">
      {/* Back */}
      <Link
        href="/teams"
        className="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-white mb-8 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 rounded-sm"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        All Teams
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-3xl font-extrabold text-white">{team.name}</h1>
            <span className="rounded-md border border-gray-700 bg-gray-800 px-2.5 py-1 text-sm font-bold tracking-widest text-gray-300">
              {team.country_code}
            </span>
          </div>
          <p className="text-gray-400">{formatStage(team.group_name)}</p>
        </div>
      </div>

      {/* Stat grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-10">
        {[
          { label: "FIFA Rank", value: `#${team.fifa_ranking}`, color: "text-white" },
          { label: "Elo Rating", value: team.elo_rating.toLocaleString(), color: "text-white" },
          { label: "Win Rate", value: winRate ? `${winRate}%` : "—", color: "text-emerald-400" },
          {
            label: "Goals",
            value: `${team.goals_for}–${team.goals_against}`,
            color: "text-white",
          },
        ].map(({ label, value, color }) => (
          <div
            key={label}
            className="rounded-xl border border-gray-800 bg-gray-900 px-4 py-5 text-center"
          >
            <p className={`text-2xl font-bold ${color}`}>{value}</p>
            <p className="text-xs text-gray-500 mt-1">{label}</p>
          </div>
        ))}
      </div>

      {/* Record */}
      {totalGames > 0 && (
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-5 mb-10">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-4">
            Record
          </h2>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-3xl font-extrabold text-emerald-400">{team.wins}</p>
              <p className="text-xs text-gray-500 mt-1">Wins</p>
            </div>
            <div>
              <p className="text-3xl font-extrabold text-amber-400">{team.draws}</p>
              <p className="text-xs text-gray-500 mt-1">Draws</p>
            </div>
            <div>
              <p className="text-3xl font-extrabold text-red-400">{team.losses}</p>
              <p className="text-xs text-gray-500 mt-1">Losses</p>
            </div>
          </div>

          {/* Win bar */}
          {totalGames > 0 && (
            <div className="mt-5 flex h-2 overflow-hidden rounded-full bg-gray-800">
              <div
                className="bg-emerald-500"
                style={{ width: `${(team.wins / totalGames) * 100}%` }}
              />
              <div
                className="bg-amber-400"
                style={{ width: `${(team.draws / totalGames) * 100}%` }}
              />
              <div
                className="bg-red-500"
                style={{ width: `${(team.losses / totalGames) * 100}%` }}
              />
            </div>
          )}
        </div>
      )}

      {/* Matches */}
      <div>
        <h2 className="text-xl font-bold text-white mb-5">Matches</h2>
        {matches.length === 0 ? (
          <EmptyState title="No matches found" message="No fixtures scheduled for this team yet." />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {matches
              .sort(
                (a, b) =>
                  new Date(a.kickoff_at).getTime() - new Date(b.kickoff_at).getTime(),
              )
              .map((match) => (
                <MatchCard
                  key={match.id}
                  match={match}
                  homeTeam={teamMap.get(match.home_team_id)}
                  awayTeam={teamMap.get(match.away_team_id)}
                />
              ))}
          </div>
        )}
      </div>
    </div>
  );
}
