import { ForecastRowSkeleton } from "@/components/ui/LoadingSkeleton";

export default function ForecastLoading() {
  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 py-10">
      {/* Header skeleton */}
      <div className="mb-8 space-y-3">
        <div className="h-8 w-56 animate-pulse rounded bg-gray-800" aria-hidden="true" />
        <div className="h-4 w-full max-w-lg animate-pulse rounded bg-gray-800" aria-hidden="true" />
        <div className="h-4 w-64 animate-pulse rounded bg-gray-800" aria-hidden="true" />
      </div>

      {/* Meta bar skeleton */}
      <div className="flex gap-6 mb-8">
        {[64, 96, 80, 112].map((w) => (
          <div
            key={w}
            className={`h-3 w-${w} animate-pulse rounded bg-gray-800`}
            style={{ width: w }}
            aria-hidden="true"
          />
        ))}
      </div>

      {/* Table skeleton */}
      <div className="rounded-xl border border-gray-800 bg-gray-900 px-4 sm:px-6 py-5 mb-8">
        <div className="h-4 w-40 animate-pulse rounded bg-gray-800 mb-5" aria-hidden="true" />
        <div className="divide-y divide-gray-800/50">
          {Array.from({ length: 8 }, (_, i) => (
            <ForecastRowSkeleton key={i} />
          ))}
        </div>
      </div>
    </div>
  );
}
