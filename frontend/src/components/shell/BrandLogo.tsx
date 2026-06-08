import finAiLogo from "@brand/FinAI.png";
import finAiLogoDark from "@brand/FinAI_dark.png";
import { cn } from "@/lib/utils";

export function BrandLogo({
  className,
  imageClassName,
}: {
  className?: string;
  imageClassName?: string;
}) {
  const imageClass = cn("h-8 w-auto object-contain", imageClassName);

  return (
    <span className={cn("inline-flex items-center", className)}>
      <img
        src={finAiLogo}
        alt="Borek Finance"
        className={cn(imageClass, "dark:hidden")}
      />
      <img
        src={finAiLogoDark}
        alt="Borek Finance"
        className={cn(imageClass, "hidden dark:block")}
      />
    </span>
  );
}
