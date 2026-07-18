import type { Metadata } from "next";
import { api, type MatchRead, type TeamRead } from "@/lib/api";
import { MatchCard } from "@/components/domain/MatchCard";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { formatStage, statusLabel } from "@/lib/utils";
import type { MatchStatus } from "@/lib/api";

export const metadata: Metadata = {
  title: "Matches",
  description: "All World Cup 2026 fixtures — live, upcoming, and finished.",
};

export const dynamic = "force-dynamic";

interface SearchParams {
  status?: string;
  stage?: string;
}

interface Props {
  searchParams: Promise<SearchParams>;
}

export default async function MatchesPage({ searchParams }: Props) {
  const { status, stage } = await searchParams;

  let matches: MatchRead[] = [];
  let teamMap = new Map<number, TeamRead>();
  let error = false;

  try {
    const [matchesPage, teamsPage] = await Promise.all([
      api.matches.list({
        limit: 100,
        status: status as MatchStatus | undefined,
        stage,
      }),
      api.teams.list({ limit: 100 }),
    ]);
    matches = matchesPage.items;
    teamMap = new Map(teamsPage.items.map((t) => [t.id, t]));
  } catch {
    error = true;
  }

  // Group matches by stage for display
  const grouped = matches.reduce<Record<string, MatchRead[]>>((acc, m) => {
    const s = m.stage;
    if (!acc[s]) acc[s] = [];
    acc[s].push(m);
    return acc;
  }, {});
  const stages = Object.keys(grouped).sort();

  // Status filter tabs
  const statusFilters: Array<{ value: string | undefined; label: string }> = [
    { value: undefined, label: "All" },
    { value: "live", label: "Live" },
    { value: "scheduled", label: "Upcoming" },
    { value: "finished", label: "Finished" },
  ];

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-10">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-extrabold text-white">Matches</h1>
        {!error && (
          <p className="mt-2 text-gray-400">
            {matches.length} fixture{matches.length !== 1 ? "s" : ""}
            {status ? ` · ${statusLabel(status as MatchStatus)}` : ""}
            {stage ? ` · ${formatStage(stage)}` : ""}
          </p>
        )}
      </div>

      {/* Status filter tabs */}
      <div className="flex flex-wrap gap-2 mb-8" role="tablist" aria-label="Filter matches by status">
        {statusFilters.map(({ value, label }) => {
          const isActive = status === value || (!status && !value);
          const href = value ? `/matches?status=${value}` : "/matches";
          return (
            <a
              key={label}
              href={href}
              role="tab"
              aria-selected={isActive}
              className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 ${
                isActive
                  ? "border-emerald-500 bg-emerald-500/10 text-emerald-400"
                  : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-white"
              }`}
            >
              {label}
            </a>
          );
        })}
      </div>

      {error ? (
        <ErrorState message="Could not load matches. Make sure the API is running." />
      ) : matches.length === 0 ? (
        <EmptyState
          title="No matches found"
          message={status ? `No ${statusLabel(status as MatchStatus).toLowerCase()} matches right now.` : "No fixtures have been loaded yet."}
        />
      ) : (
        <div className="space-y-10">
          {stages.map((s) => (
            <section key={s}>
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-emerald-400">
                {formatStage(s)}
              </h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {grouped[s]
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
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
