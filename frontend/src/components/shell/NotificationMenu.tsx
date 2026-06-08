import { Link } from "react-router-dom";
import { Bell } from "lucide-react";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { cn } from "@/lib/utils";
import { useNotificationSummary } from "@/hooks/useNotificationSummary";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

type NotificationMenuProps = {
  enabled: boolean;
};

export function NotificationMenu({ enabled }: NotificationMenuProps) {
  const { items, total, loading, reload } = useNotificationSummary(enabled);

  if (!enabled) {
    return null;
  }

  return (
    <DropdownMenu onOpenChange={(open) => open && void reload()}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={
            total > 0
              ? `${total} notification${total === 1 ? "" : "s"}`
              : "Notifications"
          }
          className="relative grid h-8 w-8 place-items-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground"
        >
          <Bell className="h-4 w-4" />
          {total > 0 ? (
            <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-destructive" />
          ) : null}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-72">
        <DropdownMenuLabel className="text-[13px] font-medium">
          Notifications
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {loading && items.length === 0 ? (
          <LoadingSpinner
            centered
            size="sm"
            className="text-muted-foreground"
            label="Loading…"
            containerClassName="px-2 py-3"
          />
        ) : items.length === 0 ? (
          <p className="px-2 py-3 text-[12px] text-muted-foreground">
            Nothing needs attention right now.
          </p>
        ) : (
          items.map((item) => (
            <DropdownMenuItem key={item.id} asChild>
              <Link
                to={item.href}
                className={cn(
                  "flex cursor-pointer flex-col items-start gap-0.5 py-2",
                )}
              >
                <span className="text-[13px] font-medium text-foreground">
                  {item.title}
                </span>
                <span className="text-[11px] text-muted-foreground">
                  {item.description}
                </span>
              </Link>
            </DropdownMenuItem>
          ))
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
