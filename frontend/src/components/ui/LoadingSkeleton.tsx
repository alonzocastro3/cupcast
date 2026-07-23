import React from "react";

function Bone({ className }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded bg-gray-800 ${className ?? ""}`}
      aria-hidden="true"
    />
  );
}

export function TeamCardSkeleton() {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5 space-y-4">
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <Bone className="h-5 w-24" />
          <Bone className="h-4 w-16" />
        </div>
        <Bone className="h-8 w-12 rounded-md" />
      </div>
      <div className="grid grid-cols-3 gap-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="space-y-1">
            <Bone className="h-4 w-full" />
            <Bone className="h-3 w-2/3" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function MatchCardSkeleton() {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5 space-y-4">
      <div className="flex items-center justify-between">
        <Bone className="h-4 w-20" />
        <Bone className="h-5 w-14 rounded-full" />
      </div>
      <div className="flex items-center gap-4">
        <div className="flex-1 space-y-2">
          <Bone className="h-5 w-full" />
        </div>
        <Bone className="h-6 w-8" />
        <div className="flex-1 space-y-2">
          <Bone className="h-5 w-full" />
        </div>
      </div>
      <Bone className="h-4 w-32" />
    </div>
  );
}

export function ForecastRowSkeleton() {
  return (
    <div className="flex items-center gap-4 px-4 py-3 border-b border-gray-800">
      <Bone className="h-4 w-4 flex-shrink-0" />
      <div className="flex-1 space-y-1">
        <Bone className="h-4 w-28" />
        <Bone className="h-2 w-16" />
      </div>
      <Bone className="h-4 w-10 hidden sm:block" />
      <div className="hidden sm:block space-y-1 w-20">
        <Bone className="h-3 w-10" />
        <Bone className="h-1.5 w-full" />
      </div>
      <div className="hidden sm:block space-y-1 w-20">
        <Bone className="h-3 w-10" />
        <Bone className="h-1.5 w-full" />
      </div>
      <div className="space-y-1 w-20">
        <Bone className="h-3 w-10" />
        <Bone className="h-1.5 w-full" />
      </div>
    </div>
  );
}

export function GridSkeleton({
  count = 6,
  Card,
}: {
  count?: number;
  Card: () => React.ReactElement;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }, (_, i) => (
        <Card key={i} />
      ))}
    </div>
  );
}
