import { cn } from "@/lib/utils";

type LoadingSpinnerSize = "sm" | "md" | "lg" | "xl";

const sizeClasses: Record<LoadingSpinnerSize, string> = {
  sm: "loader-sm",
  md: "loader-md",
  lg: "loader-lg",
  xl: "loader-xl",
};

type LoadingSpinnerProps = {
  size?: LoadingSpinnerSize;
  className?: string;
  /** Center the spinner in its container (for page/section loading). */
  centered?: boolean;
  label?: string;
  containerClassName?: string;
};

/** Consistent spinner for list/tab section loading (documents, matching, bank statements, manual review). */
export function SectionLoadingSpinner({ label }: { label?: string }) {
  return (
    <LoadingSpinner
      centered
      size="lg"
      className="text-muted-foreground"
      label={label}
      containerClassName="py-16"
    />
  );
}

export function LoadingSpinner({
  size = "xl",
  className,
  centered = false,
  label,
  containerClassName,
}: LoadingSpinnerProps) {
  const spinner = (
    <span
      className={cn("loader", sizeClasses[size], className)}
      role="status"
      aria-label="Loading"
    />
  );

  if (!centered && !label) {
    return spinner;
  }

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-2 py-16",
        containerClassName,
      )}
    >
      {spinner}
      {label ? (
        <p className="text-[13px] text-muted-foreground">{label}</p>
      ) : null}
    </div>
  );
}
