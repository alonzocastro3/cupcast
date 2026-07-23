import type { SentimentLabel } from "@/lib/api";

interface Props {
  score: number; // -1.0 to 1.0
  label: SentimentLabel;
}

// Track coordinates (SVG viewBox 0 0 200 32)
const LEFT = 10;
const RIGHT = 190;
const WIDTH = RIGHT - LEFT; // 180
const TRACK_Y = 18;
const TRACK_H = 4;
const CENTER_X = LEFT + WIDTH / 2; // 100

const COLORS: Record<SentimentLabel, string> = {
  positive: "#10b981",
  neutral: "#9ca3af",
  negative: "#f87171",
};

function scoreToX(score: number): number {
  const clamped = Math.max(-1, Math.min(1, score));
  return LEFT + ((clamped + 1) / 2) * WIDTH;
}

export function SentimentGauge({ score, label }: Props) {
  const thumbX = scoreToX(score);
  const barLeft = Math.min(thumbX, CENTER_X);
  const barWidth = Math.abs(thumbX - CENTER_X);
  const color = COLORS[label];
  const sign = score >= 0 ? "+" : "";

  return (
    <div
      role="img"
      aria-label={`Sentiment score ${sign}${score.toFixed(2)}, ${label}`}
      className="w-full"
    >
      <svg
        viewBox="0 0 200 32"
        className="w-full overflow-visible"
        aria-hidden="true"
        focusable={false}
      >
        {/* Axis labels */}
        <text x={LEFT} y={TRACK_Y - 7} fontSize="7" fill="#4b5563" textAnchor="middle" fontFamily="ui-monospace, monospace">−1</text>
        <text x={CENTER_X} y={TRACK_Y - 7} fontSize="7" fill="#4b5563" textAnchor="middle" fontFamily="ui-monospace, monospace">0</text>
        <text x={RIGHT} y={TRACK_Y - 7} fontSize="7" fill="#4b5563" textAnchor="middle" fontFamily="ui-monospace, monospace">+1</text>

        {/* Track background */}
        <rect
          x={LEFT}
          y={TRACK_Y}
          width={WIDTH}
          height={TRACK_H}
          rx={TRACK_H / 2}
          fill="#1f2937"
        />

        {/* Colored fill from center to thumb */}
        {barWidth > 0 && (
          <rect
            x={barLeft}
            y={TRACK_Y}
            width={barWidth}
            height={TRACK_H}
            rx={TRACK_H / 2}
            fill={color}
          />
        )}

        {/* Center zero mark */}
        <line
          x1={CENTER_X}
          y1={TRACK_Y - 2}
          x2={CENTER_X}
          y2={TRACK_Y + TRACK_H + 2}
          stroke="#374151"
          strokeWidth="1.5"
        />

        {/* Thumb */}
        <circle
          cx={thumbX}
          cy={TRACK_Y + TRACK_H / 2}
          r={6}
          fill={color}
          stroke="#030712"
          strokeWidth="1.5"
        />
      </svg>
    </div>
  );
}
