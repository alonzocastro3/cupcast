import { TeamCardSkeleton } from "@/components/ui/LoadingSkeleton";

export default function TeamsLoading() {
  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-10">
      <div className="mb-8 space-y-2">
        <div className="h-8 w-32 animate-pulse rounded bg-gray-800" />
        <div className="h-4 w-48 animate-pulse rounded bg-gray-800" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 8 }, (_, i) => (
          <TeamCardSkeleton key={i} />
        ))}
      </div>
    </div>
  );
}
