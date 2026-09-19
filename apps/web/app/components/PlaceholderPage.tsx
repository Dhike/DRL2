export default function PlaceholderPage({
  title,
  description,
  phase,
}: {
  title: string;
  description: string;
  phase: string;
}) {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="mt-2 text-sm opacity-70">{description}</p>
      <div className="mt-6 rounded-lg border border-dashed border-current/20 p-6 text-sm opacity-70">
        Coming in {phase}.
      </div>
    </div>
  );
}
