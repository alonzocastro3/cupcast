import type {
  ArticleSentimentRead,
  SentimentLabel,
  SentimentMetadata,
  TeamSentimentRead,
} from "@/lib/api";
import { SentimentGauge } from "./SentimentGauge";

interface Props {
  team: TeamSentimentRead;
  metadata: SentimentMetadata;
  /** ISO string from the server render — used for "last updated" display. */
  fetchedAt: string;
}

// ── Visual tokens per label ───────────────────────────────────────────────────

const LABEL_STYLES: Record<
  SentimentLabel,
  { score: string; badge: string; dot: string; bar: string }
> = {
  positive: {
    score: "text-emerald-400",
    badge: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
    dot: "bg-emerald-500",
    bar: "bg-emerald-500",
  },
  neutral: {
    score: "text-gray-400",
    badge: "text-gray-400 bg-gray-500/10 border-gray-600/30",
    dot: "bg-gray-500",
    bar: "bg-gray-500",
  },
  negative: {
    score: "text-red-400",
    badge: "text-red-400 bg-red-500/10 border-red-500/30",
    dot: "bg-red-500",
    bar: "bg-red-500",
  },
};

// ── Distribution sub-component ────────────────────────────────────────────────

function ArticleDistribution({ articles }: { articles: ArticleSentimentRead[] }) {
  if (articles.length === 0) return null;

  const total = articles.length;
  const counts = { positive: 0, neutral: 0, negative: 0 } as Record<SentimentLabel, number>;
  for (const a of articles) counts[a.label]++;

  const rows: { label: SentimentLabel; display: string }[] = [
    { label: "positive", display: "Positive" },
    { label: "neutral", display: "Neutral" },
    { label: "negative", display: "Negative" },
  ];

  return (
    <div>
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-3">
        Article breakdown
      </p>

      {/* Stacked bar overview */}
      <div
        className="flex h-2 w-full overflow-hidden rounded-full bg-gray-800 mb-4"
        role="img"
        aria-label={`${counts.positive} positive, ${counts.neutral} neutral, ${counts.negative} negative articles`}
      >
        <div className="bg-emerald-500 h-full" style={{ width: `${(counts.positive / total) * 100}%` }} />
        <div className="bg-gray-500 h-full" style={{ width: `${(counts.neutral / total) * 100}%` }} />
        <div className="bg-red-500 h-full" style={{ width: `${(counts.negative / total) * 100}%` }} />
      </div>

      {/* Per-label rows */}
      <div className="space-y-2">
        {rows.map(({ label, display }) => {
          const count = counts[label];
          const pct = (count / total) * 100;
          const styles = LABEL_STYLES[label];
          return (
            <div key={label} className="flex items-center gap-2.5 text-xs">
              <div className={`h-2 w-2 rounded-full flex-shrink-0 ${styles.dot}`} aria-hidden="true" />
              <span className="text-gray-400 w-14">{display}</span>
              <div className="flex-1 h-1.5 rounded-full bg-gray-800 overflow-hidden">
                <div className={`h-full rounded-full ${styles.bar}`} style={{ width: `${pct}%` }} />
              </div>
              <span className="font-mono w-16 text-right text-gray-400">
                {pct.toFixed(0)}%{" "}
                <span className="text-gray-600 text-[10px]">({count})</span>
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function SentimentCard({ team, metadata, fetchedAt }: Props) {
  const styles = LABEL_STYLES[team.label];
  const sign = team.average_score >= 0 ? "+" : "";
  const scoreDisplay = `${sign}${team.average_score.toFixed(2)}`;
  const confidencePct = `${(team.confidence * 100).toFixed(0)}%`;

  const updatedTime = new Date(fetchedAt).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <section
      aria-labelledby="sentiment-heading"
      className="rounded-xl border border-gray-800 bg-gray-900 p-5"
    >
      {/* ── Header ── */}
      <div className="flex items-center justify-between mb-5">
        <h2
          id="sentiment-heading"
          className="text-sm font-semibold text-gray-400 uppercase tracking-widest"
        >
          News Sentiment
        </h2>

        {/* Methodology disclosure — <details>/<summary> is keyboard-accessible with no JS */}
        <details className="relative">
          <summary
            className="flex h-5 w-5 cursor-pointer items-center justify-center rounded-full border border-gray-700 text-[10px] font-bold text-gray-500 transition-colors hover:border-gray-500 hover:text-gray-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 [list-style:none] [&::marker]:hidden [&::-webkit-details-marker]:hidden select-none"
            aria-label="Sentiment methodology"
          >
            ?
          </summary>
          <div
            className="absolute right-0 z-10 mt-2 w-72 rounded-xl border border-gray-700 bg-gray-800 p-4 text-xs leading-relaxed shadow-2xl"
            role="tooltip"
          >
            <p className="font-semibold text-white mb-2">How scores are calculated</p>
            <p className="text-gray-300 mb-2">
              Each article title and summary is scored by{" "}
              <strong className="text-white">VADER</strong> (Valence Aware Dictionary and
              sEntiment Reasoner), a deterministic rule-based lexicon — no neural network,
              no paid API, no training data.
            </p>
            <p className="text-gray-300 mb-3">
              Scores range from <strong className="text-white">−1</strong> (most negative)
              to <strong className="text-white">+1</strong> (most positive). Team scores
              average all matching articles.
            </p>
            <p className="text-gray-500">
              Analyzer: {metadata.analyzer}
              <br />
              Cache TTL: 5 min · {metadata.sample_size} articles in feed
            </p>
          </div>
        </details>
      </div>

      {/* ── Score + label ── */}
      <div className="flex items-center gap-3 mb-5">
        <span
          className={`text-3xl font-extrabold font-mono tabular-nums ${styles.score}`}
          aria-label={`Sentiment score ${scoreDisplay}`}
        >
          {scoreDisplay}
        </span>
        <span
          className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold capitalize ${styles.badge}`}
        >
          {team.label}
        </span>
        <span className="ml-auto text-xs text-gray-600">
          {team.article_count} article{team.article_count !== 1 ? "s" : ""}
        </span>
      </div>

      {/* ── Gauge ── */}
      <div className="mb-5">
        <SentimentGauge score={team.average_score} label={team.label} />
      </div>

      {/* ── Per-article distribution (only on single-team response) ── */}
      {team.articles.length > 0 && (
        <div className="mb-5 pt-4 border-t border-gray-800">
          <ArticleDistribution articles={team.articles} />
        </div>
      )}

      {/* ── Confidence + last updated ── */}
      <div className="flex items-center justify-between pt-4 border-t border-gray-800 mb-4 text-xs text-gray-600">
        <span>
          Confidence:{" "}
          <span className="text-gray-400 font-semibold">{confidencePct}</span>
        </span>
        <span>Updated {updatedTime}</span>
      </div>

      {/* ── Limitations disclaimer ── */}
      <p className="text-xs text-gray-600 leading-relaxed" role="note">
        <span className="text-amber-500/70 mr-1" aria-hidden="true">⚠</span>
        {metadata.disclaimer}
      </p>
    </section>
  );
}
