import Link from "next/link";
import type { Metadata } from "next";
import { api, type TeamRead } from "@/lib/api";
import { MatchCard } from "@/components/domain/MatchCard";
import { TeamCard } from "@/components/domain/TeamCard";
import { ProbabilityBar } from "@/components/domain/ProbabilityBar";
import { PredictionBadge } from "@/components/domain/PredictionBadge";
import { EmptyState } from "@/components/ui/EmptyState";

export const metadata: Metadata = {
  title: "CupCast — World Cup Prediction Dashboard",
  description:
    "Live match intelligence, model-powered win probabilities, and community predictions for the World Cup.",
};

export const dynamic = "force-dynamic";

async function getHomeData() {
  try {
    const [teamsPage, matchesPage] = await Promise.all([
      api.teams.list({ limit: 100 }),
      api.matches.list({ limit: 100 }),
    ]);

    const teamMap = new Map<number, TeamRead>(teamsPage.items.map((t) => [t.id, t]));

    const upcomingMatches = matchesPage.items
      .filter((m) => m.status === "scheduled")
      .slice(0, 3);

    const liveMatches = matchesPage.items.filter((m) => m.status === "live").slice(0, 3);

    const topTeams = [...teamsPage.items]
      .sort((a, b) => b.elo_rating - a.elo_rating)
      .slice(0, 4);

    // Fetch model predictions for upcoming matches
    const predictionResults = await Promise.allSettled(
      upcomingMatches.map((m) => api.matches.modelPrediction(m.id)),
    );
    const predictions = predictionResults
      .map((r) => (r.status === "fulfilled" ? r.value : null))
      .filter(Boolean);

    return {
      teamMap,
      upcomingMatches,
      liveMatches,
      topTeams,
      predictions,
      totalTeams: teamsPage.total,
      totalMatches: matchesPage.total,
      groups: [...new Set(teamsPage.items.map((t) => t.group_name))].length,
    };
  } catch {
    return null;
  }
}

export default async function HomePage() {
  const data = await getHomeData();

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-10 space-y-20">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <section className="text-center pt-10 pb-6">
        <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-1.5 text-xs font-medium text-emerald-400 mb-8">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
          </span>
          World Cup 2026 · Live Intelligence
        </div>

        <h1 className="text-5xl sm:text-7xl font-extrabold tracking-tight mb-6">
          <span className="bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">
            Cup
          </span>
          <span className="bg-gradient-to-r from-emerald-400 to-emerald-600 bg-clip-text text-transparent">
            Cast
          </span>
        </h1>

        <p className="mx-auto max-w-xl text-gray-400 text-lg mb-10 leading-relaxed">
          Model-powered win probabilities, community predictions, and live match intelligence
          for every World Cup fixture.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            href="/matches"
            className="rounded-lg bg-emerald-500 px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-emerald-500/20 transition-all hover:bg-emerald-400 hover:shadow-emerald-400/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-950"
          >
            View Matches
          </Link>
          <Link
            href="/teams"
            className="rounded-lg border border-gray-700 px-6 py-2.5 text-sm font-semibold text-gray-300 transition-all hover:border-gray-500 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-950"
          >
            Browse Teams
          </Link>
        </div>
      </section>

      {/* ── Tournament Overview ───────────────────────────────────────────── */}
      {data && (
        <section>
          <div className="grid grid-cols-3 gap-4 sm:gap-6">
            {[
              { label: "Teams", value: data.totalTeams, color: "text-emerald-400" },
              { label: "Matches", value: data.totalMatches, color: "text-amber-400" },
              { label: "Groups", value: data.groups, color: "text-violet-400" },
            ].map(({ label, value, color }) => (
              <div
                key={label}
                className="rounded-xl border border-gray-800 bg-gray-900 px-4 py-6 text-center"
              >
                <p className={`text-3xl font-extrabold ${color}`}>{value}</p>
                <p className="text-sm text-gray-400 mt-1">{label}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Live Matches ──────────────────────────────────────────────────── */}
      {data && data.liveMatches.length > 0 && (
        <section>
          <div className="flex items-center gap-2 mb-6">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-red-500" />
            </span>
            <h2 className="text-xl font-bold text-white">Live Now</h2>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.liveMatches.map((match) => (
              <MatchCard
                key={match.id}
                match={match}
                homeTeam={data.teamMap.get(match.home_team_id)}
                awayTeam={data.teamMap.get(match.away_team_id)}
              />
            ))}
          </div>
        </section>
      )}

      {/* ── Upcoming Matches ──────────────────────────────────────────────── */}
      <section>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-white">Upcoming Matches</h2>
          <Link
            href="/matches?status=scheduled"
            className="text-sm text-emerald-400 hover:text-emerald-300 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 rounded-sm"
          >
            See all →
          </Link>
        </div>

        {!data ? (
          <div className="rounded-xl border border-gray-800 bg-gray-900 p-6">
            <EmptyState
              title="Backend unavailable"
              message="Start the API server to load live match data."
              icon="🔌"
            />
          </div>
        ) : data.upcomingMatches.length === 0 ? (
          <EmptyState title="No upcoming matches" message="Check back soon." />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.upcomingMatches.map((match) => (
              <MatchCard
                key={match.id}
                match={match}
                homeTeam={data.teamMap.get(match.home_team_id)}
                awayTeam={data.teamMap.get(match.away_team_id)}
              />
            ))}
          </div>
        )}
      </section>

      {/* ── Model Favorites ───────────────────────────────────────────────── */}
      {data && data.predictions.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold text-white">Model Predictions</h2>
            <Link
              href="/matches"
              className="text-sm text-emerald-400 hover:text-emerald-300 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 rounded-sm"
            >
              All matches →
            </Link>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.predictions.map((pred) => {
              if (!pred) return null;
              return (
                <Link
                  key={pred.match_id}
                  href={`/matches/${pred.match_id}`}
                  className="group block rounded-xl border border-gray-800 bg-gray-900 p-5 transition-all duration-200 hover:border-emerald-500/50 hover:bg-gray-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
                >
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm font-semibold text-white">
                      {pred.home_team.name}{" "}
                      <span className="text-gray-500">vs</span>{" "}
                      {pred.away_team.name}
                    </span>
                    <PredictionBadge outcome={pred.predicted_outcome} size="sm" />
                  </div>
                  <ProbabilityBar prediction={pred} compact />
                </Link>
              );
            })}
          </div>
        </section>
      )}

      {/* ── Top Teams by Elo ─────────────────────────────────────────────── */}
      {data && data.topTeams.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-xl font-bold text-white">Top Teams</h2>
              <p className="text-sm text-gray-400 mt-1">Ranked by Elo rating</p>
            </div>
            <Link
              href="/teams"
              className="text-sm text-emerald-400 hover:text-emerald-300 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 rounded-sm"
            >
              All teams →
            </Link>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {data.topTeams.map((team) => (
              <TeamCard key={team.id} team={team} />
            ))}
          </div>
        </section>
      )}

      {/* ── How It Works ─────────────────────────────────────────────────── */}
      <section className="rounded-2xl border border-gray-800 bg-gray-900 p-8 sm:p-10">
        <h2 className="text-xl font-bold text-white mb-2">How predictions work</h2>
        <p className="text-gray-400 text-sm mb-8 max-w-2xl">
          CupCast uses a deterministic, explainable scoring model — no black-box machine learning.
          Every probability is derived from five weighted team features.
        </p>

        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {[
            {
              icon: "📊",
              title: "Five features",
              desc: "Attacking output, defensive record, FIFA ranking, Elo rating, and recent form are normalized into [0, 1] scores.",
            },
            {
              icon: "⚖️",
              title: "Weighted scoring",
              desc: "Elo and attacking strength carry 25% each; defensive and ranking 20% each; form and win rate 5% each.",
            },
            {
              icon: "🏠",
              title: "Home advantage",
              desc: "A +5% bonus is applied to the home team's raw score before computing final probabilities.",
            },
            {
              icon: "🔢",
              title: "Softmax normalization",
              desc: "Raw scores are passed through softmax so home win + draw + away win always sums to exactly 100%.",
            },
            {
              icon: "🎯",
              title: "Confidence score",
              desc: "Shows how far the leading probability rises above a uniform three-way split. Higher = more decisive.",
            },
            {
              icon: "💬",
              title: "Plain-English explanation",
              desc: "Every prediction includes a human-readable breakdown of the key factors driving the model's pick.",
            },
          ].map(({ icon, title, desc }) => (
            <div key={title} className="flex gap-3">
              <span className="text-2xl flex-shrink-0">{icon}</span>
              <div>
                <h3 className="text-sm font-semibold text-white mb-1">{title}</h3>
                <p className="text-xs text-gray-400 leading-relaxed">{desc}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-8 pt-6 border-t border-gray-800">
          <Link
            href="/about"
            className="text-sm text-emerald-400 hover:text-emerald-300 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 rounded-sm"
          >
            Read the full methodology →
          </Link>
        </div>
      </section>
    </div>
  );
}
