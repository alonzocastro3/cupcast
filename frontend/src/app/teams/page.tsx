import type { Metadata } from "next";
import { api } from "@/lib/api";
import { TeamCard } from "@/components/domain/TeamCard";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";

export const metadata: Metadata = {
  title: "Teams",
  description: "All World Cup 2026 teams with rankings, Elo ratings, and stats.",
};

export const dynamic = "force-dynamic";

export default async function TeamsPage() {
  let teams;
  try {
    const page = await api.teams.list({ limit: 100 });
    teams = page.items;
  } catch {
    return (
      <div className="mx-auto max-w-6xl px-4 sm:px-6 py-10">
        <ErrorState message="Could not load teams. Make sure the API is running." />
      </div>
    );
  }

  // Group by group_name
  const groups = teams.reduce<Record<string, typeof teams>>((acc, team) => {
    const g = team.group_name;
    if (!acc[g]) acc[g] = [];
    acc[g].push(team);
    return acc;
  }, {});

  const sortedGroupNames = Object.keys(groups).sort();

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-10">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-extrabold text-white">Teams</h1>
        <p className="mt-2 text-gray-400">
          {teams.length} team{teams.length !== 1 ? "s" : ""} across {sortedGroupNames.length} group
          {sortedGroupNames.length !== 1 ? "s" : ""}
        </p>
      </div>

      {teams.length === 0 ? (
        <EmptyState
          title="No teams yet"
          message="Seed the database to populate team data."
        />
      ) : (
        <div className="space-y-10">
          {sortedGroupNames.map((groupName) => (
            <section key={groupName}>
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-emerald-400">
                {groupName.replace(/_/g, " ")}
              </h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {groups[groupName]
                  .sort((a, b) => a.fifa_ranking - b.fifa_ranking)
                  .map((team) => (
                    <TeamCard key={team.id} team={team} />
                  ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
