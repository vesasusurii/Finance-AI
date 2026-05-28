import finAiLogo from "@brand/FinAI.png";
import { cn } from "@/lib/utils";

export function BrandLogo({
  className,
  imageClassName,
}: {
  className?: string;
  imageClassName?: string;
}) {
  return (
    <span className={cn("inline-flex items-center", className)}>
      <img
        src={finAiLogo}
        alt="Borek Finance"
        className={cn("h-8 w-auto object-contain", imageClassName)}
      />
    </span>
  );
}
