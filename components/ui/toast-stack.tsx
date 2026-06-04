"use client";

import { CheckCircle2, Info, X, XCircle } from "lucide-react";
import type { ToastItem, ToastType } from "@/lib/use-toast";
import { cn } from "@/lib/utils";

const iconByType: Record<ToastType, typeof Info> = {
  info: Info,
  success: CheckCircle2,
  error: XCircle,
};

const styleByType: Record<ToastType, string> = {
  info: "border-terminal-border text-foreground",
  success: "border-terminal-green/50 text-terminal-green",
  error: "border-terminal-red/50 text-terminal-red",
};

interface ToastStackProps {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
}

export function ToastStack({ toasts, onDismiss }: ToastStackProps) {
  if (toasts.length === 0) return null;

  return (
    <div
      className="pointer-events-none fixed bottom-24 left-1/2 z-[100] flex w-full max-w-md -translate-x-1/2 flex-col gap-2 px-4"
      aria-live="polite"
    >
      {toasts.map((toast) => {
        const Icon = iconByType[toast.type];
        return (
          <div
            key={toast.id}
            className={cn(
              "pointer-events-auto flex items-start gap-2 rounded-md border bg-terminal-panel/95 px-3 py-2.5 font-mono text-xs shadow-lg backdrop-blur-sm",
              styleByType[toast.type]
            )}
          >
            <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <p className="min-w-0 flex-1 leading-relaxed">{toast.message}</p>
            <button
              type="button"
              onClick={() => onDismiss(toast.id)}
              className="shrink-0 text-muted-foreground hover:text-foreground"
              aria-label="关闭提示"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
