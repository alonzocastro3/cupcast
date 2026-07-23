import type { Metadata } from "next";
import { api, ApiError } from "@/lib/api";
import { ForecastTable } from "@/components/domain/ForecastTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";

export const metadata: Metadata = {
  title: "Tournament Forecast",
  description:
    "Monte Carlo championship probability rankings for the World Cup 2026 — estimated from 1,000 simulated tournaments.",
};

export const dynamic = "force-dynamic";

export default async function ForecastPage() {
  let data;
  try {
    data = await api.simulations.tournament({ n: 1000 });
  } catch (e) {
    if (e instanceof ApiError && e.status === 503) {
      return (
        <div className="mx-auto max-w-4xl px-4 sm:px-6 py-10">
          <EmptyState
            title="No teams seeded yet"
            message="Run the database seed script to populate team data before generating forecasts."
            icon="📊"
          />
        </div>
      );
    }
    return (
      <div className="mx-auto max-w-4xl px-4 sm:px-6 py-10">
        <ErrorState message="Could not load the tournament forecast. Make sure the API is running." />
      </div>
    );
  }

  const updatedTime = new Date(data.generated_at).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
  const updatedDate = new Date(data.generated_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 py-10">
      {/* ── Header ── */}
      <div className="mb-8">
        <h1 className="text-3xl font-extrabold text-white mb-2">Tournament Forecast</h1>
        <p className="text-gray-400 leading-relaxed max-w-2xl">
          Championship probability rankings estimated from{" "}
          <span className="text-white font-semibold">
            {data.simulation_count.toLocaleString()} simulated tournaments
          </span>
          . Each simulation runs a full round-robin group stage and single-elimination knockout
          bracket using the CupCast prediction model.
        </p>
      </div>

      {/* ── Meta bar ── */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 mb-8 text-xs text-gray-500">
        <span>
          Model{" "}
          <span className="font-mono text-gray-400">v{data.model_version}</span>
        </span>
        <span>
          {data.simulation_count.toLocaleString()} simulations
        </span>
        <span>
          Seed{" "}
          <span className="font-mono text-gray-400">{data.random_seed}</span>
        </span>
        <span>
          Updated{" "}
          <span className="text-gray-400">
            {updatedDate} at {updatedTime}
          </span>
        </span>
      </div>

      {/* ── Table ── */}
      {data.teams.length === 0 ? (
        <EmptyState title="No teams found" message="No tournament data available." />
      ) : (
        <section
          aria-labelledby="forecast-table-heading"
          className="rounded-xl border border-gray-800 bg-gray-900 px-4 sm:px-6 py-5 mb-8"
        >
          <h2
            id="forecast-table-heading"
            className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-5"
          >
            Probability Rankings
          </h2>
          <ForecastTable teams={data.teams} />

          {/* Column legend */}
          <div className="mt-5 pt-4 border-t border-gray-800 flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-gray-600">
            <span>
              <span className="inline-block w-2 h-2 rounded-full bg-sky-500 mr-1.5" aria-hidden="true" />
              Group Adv — probability of finishing top 2 in group
            </span>
            <span>
              <span className="inline-block w-2 h-2 rounded-full bg-violet-500 mr-1.5" aria-hidden="true" />
              Final — probability of reaching the final
            </span>
            <span>
              <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1.5" aria-hidden="true" />
              Champion — probability of winning the tournament
            </span>
          </div>
        </section>
      )}

      {/* ── Methodology disclosure ── */}
      <section className="rounded-xl border border-gray-800 bg-gray-900 p-5 mb-8">
        <details>
          <summary className="flex cursor-pointer items-center justify-between list-none [&::-webkit-details-marker]:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 rounded-sm">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest">
              How forecasts are calculated
            </h2>
            <svg
              className="h-4 w-4 text-gray-600 transition-transform details-open:rotate-180"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </summary>

          <div className="mt-5 space-y-4 text-sm text-gray-400 leading-relaxed">
            <p>
              Each simulation independently samples a complete tournament outcome using the{" "}
              <strong className="text-white">CupCast prediction model</strong> — a deterministic
              weighted scoring model that outputs win/draw/loss probabilities for any pair of teams.
            </p>

            <div className="space-y-3">
              <div className="rounded-lg border border-gray-800 bg-gray-800/50 px-4 py-3">
                <p className="font-semibold text-white text-xs uppercase tracking-widest mb-1.5">
                  Group stage
                </p>
                <p className="text-xs">
                  Round-robin within each group. Match outcomes are sampled from the model
                  probabilities. Goal counts are generated synthetically for tie-breaking only
                  (winner draws U[1,4] goals, loser draws U[0,winner−1]; draws draw U[0,3] each).
                  Tie-breaking order: points → goal difference → goals scored → alphabetical team code.
                </p>
              </div>

              <div className="rounded-lg border border-gray-800 bg-gray-800/50 px-4 py-3">
                <p className="font-semibold text-white text-xs uppercase tracking-widest mb-1.5">
                  Knockout bracket
                </p>
                <p className="text-xs">
                  Adjacent groups are paired: Group A winner vs Group B runner-up, and vice versa.
                  Drawn knockout matches are resolved by a 50/50 coin flip (penalty-shootout proxy).
                  No extra-time model is applied.
                </p>
              </div>

              <div className="rounded-lg border border-gray-800 bg-gray-800/50 px-4 py-3">
                <p className="font-semibold text-white text-xs uppercase tracking-widest mb-1.5">
                  Probability estimation
                </p>
                <p className="text-xs">
                  Each probability is the fraction of the{" "}
                  {data.simulation_count.toLocaleString()} simulations in which that team
                  reached or won the given stage. Model predictions are cached across
                  simulations — each team pair is evaluated only once.
                </p>
              </div>
            </div>

            <div>
              <p className="font-semibold text-white text-xs uppercase tracking-widest mb-2">
                Algorithm details
              </p>
              <p className="text-gray-500 text-xs font-mono leading-relaxed">
                {data.metadata.algorithm}
              </p>
            </div>

            {data.metadata.limitations.length > 0 && (
              <div>
                <p className="font-semibold text-gray-400 text-xs uppercase tracking-widest mb-2">
                  Known limitations
                </p>
                <ul className="space-y-1">
                  {data.metadata.limitations.map((lim) => (
                    <li key={lim} className="flex gap-2 text-xs text-gray-500">
                      <span className="text-gray-700 flex-shrink-0 mt-0.5">–</span>
                      {lim}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </details>
      </section>

      {/* ── Disclaimer ── */}
      <p className="text-xs text-gray-600 leading-relaxed" role="note">
        <span className="text-amber-500/70 mr-1" aria-hidden="true">⚠</span>
        Forecasts are statistical estimates generated by a rule-based model and are intended for
        entertainment and educational purposes only. They do not constitute sports betting advice and
        should not be treated as predictions of actual match outcomes. Probabilities will change as
        team statistics are updated.
      </p>
    </div>
  );
}
