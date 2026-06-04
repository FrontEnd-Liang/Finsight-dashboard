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
  "对比 AAPL 与 MSFT 营收增速及利润率",
  "汇总 NVDA 数据中心业务前景（基于公告/财报）",
  "最新 FOMC 对 2025 年降息路径释放何种信号？",
  "生成超大盘科技 KPI 对比 Markdown 表格",
];

export function ChatInput({
  onSend,
  disabled,
  placeholder = "询问财报、宏观或个股研究…",
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
        SSE 流式 · Supabase 向量检索 · DeepSeek
      </p>
    </div>
  );
}
