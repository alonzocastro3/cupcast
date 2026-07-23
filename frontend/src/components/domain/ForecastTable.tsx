"use client";

import { useMemo, useState } from "react";
import type { TeamTournamentProbabilities } from "@/lib/api";

interface Props {
  teams: TeamTournamentProbabilities[];
}

type SortKey = "championship_probability" | "final_probability" | "group_advance_probability";
type SortDir = "asc" | "desc";

// ── Probability mini-bar ──────────────────────────────────────────────────────

function ProbBar({ value, color = "bg-emerald-500" }: { value: number; color?: string }) {
  const pct = (value * 100).toFixed(1);
  return (
    <div className="space-y-1 min-w-[72px]">
      <span className="font-mono text-xs tabular-nums text-white">{pct}%</span>
      <div
        className="h-1.5 w-full rounded-full bg-gray-800"
        role="presentation"
        aria-hidden="true"
      >
        <div className={`h-full rounded-full ${color}`} style={{ width: `${value * 100}%` }} />
      </div>
    </div>
  );
}

// ── Sort header button ────────────────────────────────────────────────────────

function SortTh({
  label,
  sortKey,
  current,
  dir,
  onClick,
  className = "",
}: {
  label: string;
  sortKey: SortKey;
  current: SortKey;
  dir: SortDir;
  onClick: (key: SortKey) => void;
  className?: string;
}) {
  const active = current === sortKey;
  return (
    <th
      scope="col"
      aria-sort={active ? (dir === "desc" ? "descending" : "ascending") : "none"}
      className={className}
    >
      <button
        type="button"
        onClick={() => onClick(sortKey)}
        className={`flex items-center gap-1 text-xs font-semibold uppercase tracking-widest whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 rounded-sm ${
          active ? "text-emerald-400" : "text-gray-500 hover:text-gray-300"
        }`}
      >
        {label}
        <span aria-hidden="true" className="text-[10px]">
          {active ? (dir === "desc" ? "↓" : "↑") : "↕"}
        </span>
      </button>
    </th>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function ForecastTable({ teams }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("championship_probability");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  const sorted = useMemo(
    () =>
      [...teams].sort((a, b) => {
        const diff = a[sortKey] - b[sortKey];
        return sortDir === "desc" ? -diff : diff;
      }),
    [teams, sortKey, sortDir],
  );

  return (
    <div className="overflow-x-auto -mx-4 sm:mx-0">
      <table className="w-full min-w-[560px] border-collapse text-sm">
        <caption className="sr-only">Tournament forecast — click column headers to sort</caption>
        <thead>
          <tr className="border-b border-gray-800">
            <th scope="col" className="pl-4 sm:pl-0 pr-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-widest w-8">
              #
            </th>
            <th scope="col" className="pr-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-widest">
              Team
            </th>
            <th scope="col" className="pr-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-widest hidden sm:table-cell">
              Group
            </th>
            <SortTh
              label="Group Adv"
              sortKey="group_advance_probability"
              current={sortKey}
              dir={sortDir}
              onClick={handleSort}
              className="pr-6 py-3 text-left hidden md:table-cell"
            />
            <SortTh
              label="Final"
              sortKey="final_probability"
              current={sortKey}
              dir={sortDir}
              onClick={handleSort}
              className="pr-6 py-3 text-left hidden sm:table-cell"
            />
            <SortTh
              label="Champion"
              sortKey="championship_probability"
              current={sortKey}
              dir={sortDir}
              onClick={handleSort}
              className="pr-4 sm:pr-0 py-3 text-left"
            />
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800/50">
          {sorted.map((team, i) => (
            <tr
              key={team.team_code}
              className="hover:bg-gray-800/30 transition-colors"
            >
              {/* Rank */}
              <td className="pl-4 sm:pl-0 pr-3 py-3.5 text-xs text-gray-600 font-mono tabular-nums">
                {i + 1}
              </td>

              {/* Team */}
              <td className="pr-4 py-3.5">
                <div className="flex items-center gap-2.5">
                  <span className="rounded border border-gray-700 bg-gray-800 px-1.5 py-0.5 text-[11px] font-bold tracking-widest text-gray-300 font-mono">
                    {team.team_code}
                  </span>
                  <span className="text-white font-medium truncate max-w-[120px] sm:max-w-none">
                    {team.team_name ?? team.team_code}
                  </span>
                </div>
              </td>

              {/* Group */}
              <td className="pr-4 py-3.5 hidden sm:table-cell">
                <span className="text-xs text-gray-500">Group {team.group}</span>
              </td>

              {/* Group Advance */}
              <td className="pr-6 py-3.5 hidden md:table-cell">
                <ProbBar value={team.group_advance_probability} color="bg-sky-500" />
              </td>

              {/* Final */}
              <td className="pr-6 py-3.5 hidden sm:table-cell">
                <ProbBar value={team.final_probability} color="bg-violet-500" />
              </td>

              {/* Championship */}
              <td className="pr-4 sm:pr-0 py-3.5">
                <ProbBar value={team.championship_probability} color="bg-emerald-500" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
