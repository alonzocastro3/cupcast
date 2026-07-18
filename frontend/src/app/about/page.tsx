import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "About",
  description:
    "How CupCast builds explainable World Cup predictions using a deterministic weighted scoring model.",
};

const features = [
  {
    icon: "⚽",
    title: "Attacking strength",
    weight: "25%",
    desc: "Goals scored divided by total goals in all fixtures, normalized to [0, 1]. A team that scores 70% of combined goals earns 0.70.",
  },
  {
    icon: "🛡️",
    title: "Elo rating",
    weight: "25%",
    desc: "Passed through a sigmoid function centered at 1500: 1 / (1 + e^−((elo − 1500) / 200)). A rating of 1700 yields ≈ 0.73.",
  },
  {
    icon: "🔒",
    title: "Defensive strength",
    weight: "20%",
    desc: "1 − (goals against / total goals). A team that concedes 30% of combined goals earns 0.70.",
  },
  {
    icon: "📋",
    title: "FIFA ranking",
    weight: "20%",
    desc: "Inverse log-scaled: 1 − log(rank) / log(210). Rank #1 → 1.0; rank #100 → ~0.51; rank #200 → ~0.03.",
  },
  {
    icon: "📈",
    title: "Recent form",
    weight: "5%",
    desc: "The stored recent_form_score field clamped to [0, 1]. Reflects short-run momentum not captured by historical stats.",
  },
  {
    icon: "🏆",
    title: "Win rate",
    weight: "5%",
    desc: "Wins divided by total games played. Zero when no games have been played.",
  },
];

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 sm:px-6 py-10">
      {/* Header */}
      <div className="mb-12">
        <h1 className="text-3xl font-extrabold text-white mb-3">About CupCast</h1>
        <p className="text-gray-400 leading-relaxed">
          CupCast is a World Cup prediction dashboard built around a fully explainable, deterministic
          scoring model. No black-box ML — every probability is computed from a transparent formula
          you can read below.
        </p>
      </div>

      {/* Model overview */}
      <section className="mb-12">
        <h2 className="text-xl font-bold text-white mb-4">How the model works</h2>
        <div className="space-y-4 text-sm text-gray-400 leading-relaxed">
          <p>
            For each match, both teams receive a <strong className="text-white">strength score</strong>{" "}
            computed as a weighted sum of five normalized features. A{" "}
            <strong className="text-white">+5% home advantage</strong> bonus is then added to the
            home team&apos;s raw score.
          </p>
          <p>
            A <strong className="text-white">draw score</strong> is derived as a baseline fraction of
            the average team strength, reflecting the real-world frequency of drawn matches.
          </p>
          <p>
            The three raw scores (home, draw, away) are passed through a{" "}
            <strong className="text-white">softmax function</strong>, producing probabilities that
            always sum to exactly 100%. Values are clamped to [1%, 98%] before re-normalizing to
            prevent degenerate outputs on extreme data.
          </p>
        </div>
      </section>

      {/* Feature table */}
      <section className="mb-12">
        <h2 className="text-xl font-bold text-white mb-6">Feature breakdown</h2>
        <div className="space-y-4">
          {features.map(({ icon, title, weight, desc }) => (
            <div
              key={title}
              className="rounded-xl border border-gray-800 bg-gray-900 p-5 flex gap-4"
            >
              <span className="text-2xl flex-shrink-0 mt-0.5">{icon}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-2">
                  <h3 className="text-sm font-semibold text-white">{title}</h3>
                  <span className="rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 text-xs font-bold text-emerald-400">
                    {weight}
                  </span>
                </div>
                <p className="text-xs text-gray-400 leading-relaxed">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Formula */}
      <section className="mb-12">
        <h2 className="text-xl font-bold text-white mb-4">Formal expression</h2>
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-5 font-mono text-xs text-gray-300 leading-relaxed overflow-x-auto">
          <p className="text-gray-500 mb-3">{`/* Strength score for each team */`}</p>
          <p>score = 0.25 × attacking</p>
          <p className="ml-8">+ 0.25 × elo</p>
          <p className="ml-8">+ 0.20 × defensive</p>
          <p className="ml-8">+ 0.20 × ranking</p>
          <p className="ml-8">+ 0.05 × form</p>
          <p className="ml-8">+ 0.05 × win_rate</p>
          <p className="mt-4 text-gray-500">{`/* Apply home advantage and draw baseline */`}</p>
          <p>home_score = score(home) + 0.05</p>
          <p>draw_score = 0.30 × (home_score + away_score) / 2</p>
          <p className="mt-4 text-gray-500">{`/* Softmax → probabilities */`}</p>
          <p>[p_home, p_draw, p_away] = softmax([home_score, draw_score, away_score])</p>
        </div>
      </section>

      {/* Confidence */}
      <section className="mb-12">
        <h2 className="text-xl font-bold text-white mb-4">Confidence score</h2>
        <p className="text-sm text-gray-400 leading-relaxed mb-4">
          Confidence measures how far the leading probability rises above a uniform three-way split
          (33.3%):
        </p>
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-5 font-mono text-xs text-gray-300">
          confidence = min(1.0, (max_probability − 0.333) / 0.667)
        </div>
        <div className="mt-4 grid grid-cols-3 gap-3">
          {[
            { range: "0 – 35%", label: "Low", color: "text-gray-400" },
            { range: "35 – 60%", label: "Moderate", color: "text-amber-400" },
            { range: "60 – 100%", label: "High", color: "text-emerald-400" },
          ].map(({ range, label, color }) => (
            <div
              key={label}
              className="rounded-lg border border-gray-800 bg-gray-900/50 px-3 py-3 text-center"
            >
              <p className={`text-sm font-bold ${color}`}>{label}</p>
              <p className="text-xs text-gray-500 mt-1">{range}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Disclaimer */}
      <section className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-5">
        <h2 className="text-sm font-semibold text-amber-400 mb-2">Disclaimer</h2>
        <p className="text-xs text-gray-400 leading-relaxed">
          CupCast predictions are model-generated estimates for educational and entertainment
          purposes only. They do not constitute sports betting advice. Model accuracy depends on the
          quality and recency of the underlying team statistics.
        </p>
        {/* Escaped quote handled above — no unescaped entities in this file */}
      </section>

      <div className="mt-10 flex items-center gap-4">
        <Link
          href="/matches"
          className="rounded-lg bg-emerald-500 px-5 py-2 text-sm font-semibold text-white transition-all hover:bg-emerald-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-950"
        >
          View Predictions
        </Link>
        <Link
          href="/teams"
          className="text-sm text-emerald-400 hover:text-emerald-300 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 rounded-sm"
        >
          Browse Teams →
        </Link>
      </div>
    </div>
  );
}
