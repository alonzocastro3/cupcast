import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-gray-800 bg-gray-950 mt-auto">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 py-8">
        <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <span className="text-emerald-400">⚽</span>
            <span className="font-semibold text-gray-400 tracking-widest uppercase text-xs">
              CupCast
            </span>
            <span>·</span>
            <span>World Cup prediction dashboard</span>
          </div>

          <nav className="flex items-center gap-4" aria-label="Footer navigation">
            {[
              { href: "/matches", label: "Matches" },
              { href: "/teams", label: "Teams" },
              { href: "/about", label: "About" },
            ].map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className="text-xs text-gray-500 hover:text-gray-300 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 rounded-sm"
              >
                {label}
              </Link>
            ))}
          </nav>
        </div>

        <p className="mt-6 text-center text-xs text-gray-600">
          Predictions are model-generated estimates and do not constitute sports betting advice.
        </p>
      </div>
    </footer>
  );
}
