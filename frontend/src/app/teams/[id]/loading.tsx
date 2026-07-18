export default function TeamLoading() {
  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 py-10 space-y-6 animate-pulse">
      <div className="h-4 w-24 rounded bg-gray-800" />
      <div className="h-9 w-48 rounded bg-gray-800" />
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-24 rounded-xl bg-gray-800" />
        ))}
      </div>
      <div className="h-32 rounded-xl bg-gray-800" />
      <div className="grid gap-4 sm:grid-cols-2">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-36 rounded-xl bg-gray-800" />
        ))}
      </div>
    </div>
  );
}
