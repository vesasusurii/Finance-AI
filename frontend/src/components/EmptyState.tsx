export function EmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-card px-6 py-12 text-center">
      <h3 className="text-[15px] font-semibold text-foreground">{title}</h3>
      <p className="mx-auto mt-2 max-w-md text-[13px] text-muted-foreground">{description}</p>
    </div>
  );
}
