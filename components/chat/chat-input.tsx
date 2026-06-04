"use client";

import { useRef, useState } from "react";
import { ArrowUp, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

const SUGGESTIONS = [
  "Compare AAPL vs MSFT revenue growth and margins",
  "Summarize NVDA data center outlook from filings",
  "What does the latest FOMC signal for rate cuts in 2025?",
  "Build a markdown table of mega-cap tech KPIs",
];

export function ChatInput({
  onSend,
  disabled,
  placeholder = "Ask about earnings, macro, or equity research…",
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="border-t border-terminal-border bg-terminal-panel/80 p-4">
      <div className="mb-3 flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            disabled={disabled}
            onClick={() => onSend(s)}
            className="rounded border border-terminal-border/80 bg-background/50 px-2 py-1 font-mono text-[10px] text-muted-foreground transition hover:border-terminal-green/50 hover:text-terminal-green disabled:opacity-40"
          >
            {s}
          </button>
        ))}
      </div>
      <div className="relative flex items-end gap-2 rounded-lg border border-terminal-border bg-background/60 p-2 focus-within:border-terminal-green/50">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            e.target.style.height = "auto";
            e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
          }}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
          placeholder={placeholder}
          className={cn(
            "max-h-40 min-h-[40px] flex-1 resize-none bg-transparent px-2 py-2 text-sm",
            "placeholder:text-muted-foreground focus:outline-none disabled:opacity-50"
          )}
        />
        <Button
          type="button"
          size="icon"
          variant="terminal"
          disabled={disabled || !value.trim()}
          onClick={submit}
          className="shrink-0"
        >
          {disabled ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <ArrowUp className="h-4 w-4" />
          )}
        </Button>
      </div>
      <p className="mt-2 text-center font-mono text-[10px] text-muted-foreground/60">
        SSE stream · RAG over Supabase pgvector · DeepSeek
      </p>
    </div>
  );
}
