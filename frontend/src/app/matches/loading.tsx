import { MatchCardSkeleton } from "@/components/ui/LoadingSkeleton";

export default function MatchesLoading() {
  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-10">
      <div className="mb-8 space-y-2">
        <div className="h-8 w-36 animate-pulse rounded bg-gray-800" />
        <div className="h-4 w-24 animate-pulse rounded bg-gray-800" />
      </div>
      <div className="flex gap-2 mb-8">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-8 w-20 animate-pulse rounded-full bg-gray-800" />
        ))}
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 9 }, (_, i) => (
          <MatchCardSkeleton key={i} />
        ))}
      </div>
    </div>
  );
}
