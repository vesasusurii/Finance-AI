import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui-finance/Button";
import { cn } from "@/lib/utils";

export type ConfirmOptions = {
  title?: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "default" | "destructive";
};

export type PromptOptions = {
  title?: string;
  description: string;
  placeholder?: string;
  defaultValue?: string;
  confirmLabel?: string;
  cancelLabel?: string;
};

type ConfirmState = ConfirmOptions & {
  resolve: (value: boolean) => void;
};

type PromptState = PromptOptions & {
  resolve: (value: string | null) => void;
};

type AppDialogContextValue = {
  confirm: (options: ConfirmOptions | string) => Promise<boolean>;
  prompt: (options: PromptOptions | string) => Promise<string | null>;
};

const AppDialogContext = createContext<AppDialogContextValue | null>(null);

function DialogShell({
  title,
  description,
  onClose,
  children,
}: {
  title: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-background/80 px-4"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="app-dialog-title"
        aria-describedby={description ? "app-dialog-description" : undefined}
        className="w-full max-w-md rounded-lg border border-border bg-card p-5 shadow-lg"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2
              id="app-dialog-title"
              className="text-[15px] font-semibold text-foreground"
            >
              {title}
            </h2>
            {description ? (
              <p
                id="app-dialog-description"
                className="mt-1 text-[13px] leading-relaxed text-muted-foreground"
              >
                {description}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-8 w-8 shrink-0 place-items-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground"
            aria-label="Close dialog"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function AppDialogProvider({ children }: { children: ReactNode }) {
  const [confirmState, setConfirmState] = useState<ConfirmState | null>(null);
  const [promptState, setPromptState] = useState<PromptState | null>(null);
  const [promptValue, setPromptValue] = useState("");

  const confirm = useCallback((options: ConfirmOptions | string) => {
    const opts: ConfirmOptions =
      typeof options === "string" ? { description: options } : options;
    return new Promise<boolean>((resolve) => {
      setConfirmState({ ...opts, resolve });
    });
  }, []);

  const prompt = useCallback((options: PromptOptions | string) => {
    const opts: PromptOptions =
      typeof options === "string" ? { description: options } : options;
    return new Promise<string | null>((resolve) => {
      setPromptValue(opts.defaultValue ?? "");
      setPromptState({ ...opts, resolve });
    });
  }, []);

  const closeConfirm = (value: boolean) => {
    confirmState?.resolve(value);
    setConfirmState(null);
  };

  const closePrompt = (value: string | null) => {
    promptState?.resolve(value);
    setPromptState(null);
    setPromptValue("");
  };

  return (
    <AppDialogContext.Provider value={{ confirm, prompt }}>
      {children}

      {confirmState ? (
        <DialogShell
          title={confirmState.title ?? "Confirm"}
          description={confirmState.description}
          onClose={() => closeConfirm(false)}
        >
          <div className="flex items-center justify-end gap-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => closeConfirm(false)}
            >
              {confirmState.cancelLabel ?? "Cancel"}
            </Button>
            <Button
              type="button"
              variant={
                confirmState.variant === "destructive" ? "danger" : "primary"
              }
              onClick={() => closeConfirm(true)}
            >
              {confirmState.confirmLabel ?? "Confirm"}
            </Button>
          </div>
        </DialogShell>
      ) : null}

      {promptState ? (
        <DialogShell
          title={promptState.title ?? "Enter details"}
          description={promptState.description}
          onClose={() => closePrompt(null)}
        >
          <input
            type="text"
            value={promptValue}
            onChange={(e) => setPromptValue(e.target.value)}
            placeholder={promptState.placeholder}
            className={cn(
              "mb-4 h-9 w-full rounded-md border border-input bg-background px-3 text-[13px] text-foreground",
              "placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/40",
            )}
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter") closePrompt(promptValue);
              if (e.key === "Escape") closePrompt(null);
            }}
          />
          <div className="flex items-center justify-end gap-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => closePrompt(null)}
            >
              {promptState.cancelLabel ?? "Cancel"}
            </Button>
            <Button
              type="button"
              variant="primary"
              onClick={() => closePrompt(promptValue)}
            >
              {promptState.confirmLabel ?? "Continue"}
            </Button>
          </div>
        </DialogShell>
      ) : null}
    </AppDialogContext.Provider>
  );
}

export function useAppDialog() {
  const ctx = useContext(AppDialogContext);
  if (!ctx) {
    throw new Error("useAppDialog must be used within AppDialogProvider");
  }
  return ctx;
}
