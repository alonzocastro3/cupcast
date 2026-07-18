interface EmptyStateProps {
  title: string;
  message?: string;
  icon?: string;
}

export function EmptyState({ title, message, icon = "⚽" }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <span className="text-5xl mb-4" role="img" aria-hidden>
        {icon}
      </span>
      <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
      {message && <p className="text-gray-400 text-sm max-w-sm">{message}</p>}
    </div>
  );
}
