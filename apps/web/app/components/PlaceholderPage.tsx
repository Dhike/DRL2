import Badge from "./ui/Badge";
import Card from "./ui/Card";

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
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold">{title}</h1>
        <Badge tone="accent">Coming soon</Badge>
      </div>
      <p className="mt-2 text-sm text-muted">{description}</p>
      <Card className="mt-6 border-dashed">
        <p className="text-sm text-muted">Planned for {phase}.</p>
      </Card>
    </div>
  );
}
