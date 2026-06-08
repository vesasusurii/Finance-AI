import { useRef } from "react";
import { Calendar } from "lucide-react";
import { formatDate, isoDateFromInput } from "@/lib/labels";
import { cn } from "@/lib/utils";

export function DateTextInput({
  value,
  onChange,
  id,
  className,
  inputClassName,
  placeholder = "dd/mm/yyyy",
}: {
  value: string;
  onChange: (value: string) => void;
  id?: string;
  className?: string;
  inputClassName?: string;
  placeholder?: string;
}) {
  const pickerRef = useRef<HTMLInputElement>(null);
  const pickerValue = isoDateFromInput(value) ?? "";

  const openPicker = () => {
    const el = pickerRef.current;
    if (!el) return;
    if (typeof el.showPicker === "function") {
      el.showPicker();
      return;
    }
    el.click();
  };

  return (
    <div className={cn("relative", className)}>
      <input
        type="text"
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={cn(
          "block h-9 w-full rounded-md border border-input bg-background py-0 pl-2 pr-9 text-[13px] tabular-nums",
          "placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring/60",
          inputClassName,
        )}
      />
      <button
        type="button"
        onClick={openPicker}
        aria-label="Open calendar"
        className={cn(
          "absolute right-1 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md",
          "text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground",
          "focus:outline-none focus:ring-1 focus:ring-ring/60",
        )}
      >
        <Calendar className="h-4 w-4" />
      </button>
      <input
        ref={pickerRef}
        type="date"
        tabIndex={-1}
        aria-hidden
        value={pickerValue}
        onChange={(e) => {
          if (e.target.value) onChange(formatDate(e.target.value));
        }}
        className="pointer-events-none absolute bottom-0 right-0 h-px w-px opacity-0"
      />
    </div>
  );
}
