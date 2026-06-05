"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, RefreshCw, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { fetchSuggestions } from "@/lib/api";
import { DEFAULT_SUGGESTIONS } from "@/lib/default-suggestions";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSend: (message: string) => void;
  isStreaming?: boolean;
  onStop?: () => void;
  placeholder?: string;
  sessionId?: string;
  /** 仅手动刷新时使用，避免随每条消息重新请求 */
  recentQueries?: string[];
  /** 资料库同步后递增，触发重新拉取推荐问题 */
  refreshKey?: number;
}

const SUGGESTIONS_CACHE_PREFIX = "finsight_suggestions_v2_";

function suggestionsCacheKey(sessionId: string, refreshKey: number) {
  return `${SUGGESTIONS_CACHE_PREFIX}${sessionId}_${refreshKey}`;
}

const FALLBACK_SUGGESTIONS = [...DEFAULT_SUGGESTIONS];

export function ChatInput({
  onSend,
  isStreaming = false,
  onStop,
  placeholder = "询问财报、宏观或个股研究…",
  sessionId = "default",
  recentQueries = [],
  refreshKey = 0,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>(FALLBACK_SUGGESTIONS);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const recentQueriesRef = useRef(recentQueries);
  recentQueriesRef.current = recentQueries;

  const loadSuggestions = (
    queries: string[],
    options?: { force?: boolean; useAi?: boolean }
  ) => {
    const cacheKey = suggestionsCacheKey(sessionId, refreshKey);
    const useAi = options?.useAi ?? false;
    const cacheSuffix = useAi ? "_ai" : "";
    const fullCacheKey = `${cacheKey}${cacheSuffix}`;

    if (!options?.force) {
      try {
        const raw = sessionStorage.getItem(fullCacheKey);
        if (raw) {
          const cached = JSON.parse(raw) as string[];
          if (cached.length > 0) {
            setSuggestions(cached);
            setLoadingSuggestions(false);
            return;
          }
        }
      } catch {
        /* ignore cache parse errors */
      }
    }

    if (options?.force && abortRef.current) {
      abortRef.current.abort();
    }

    const controller = new AbortController();
    if (options?.force) {
      abortRef.current = controller;
    }

    if (!useAi) {
      setSuggestions(FALLBACK_SUGGESTIONS);
    }
    setLoadingSuggestions(useAi);

    fetchSuggestions({
      recentQueries: queries,
      useAi,
      signal: options?.force ? controller.signal : undefined,
    })
      .then((items) => {
        if (items.length > 0) {
          setSuggestions(items);
          try {
            sessionStorage.setItem(fullCacheKey, JSON.stringify(items));
          } catch {
            /* quota exceeded etc. */
          }
        }
      })
      .catch((err) => {
        if ((err as Error).name !== "AbortError") {
          setSuggestions(FALLBACK_SUGGESTIONS);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingSuggestions(false);
      });
  };

  useEffect(() => {
    loadSuggestions([]);
    // 不用 abort 取消请求，避免 React Strict Mode 导致 POST 永远完不成
  }, [sessionId, refreshKey]);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || isStreaming) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  const handlePrimaryAction = () => {
    if (isStreaming) {
      onStop?.();
      return;
    }
    submit();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="border-t border-terminal-border bg-terminal-panel/80 p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {loadingSuggestions
          ? FALLBACK_SUGGESTIONS.map((s) => (
              <span
                key={s}
                className="h-6 w-40 animate-pulse rounded border border-terminal-border/50 bg-background/30"
              />
            ))
          : suggestions.map((s) => (
              <button
                key={s}
                type="button"
                disabled={isStreaming}
                onClick={() => onSend(s)}
                className="rounded border border-terminal-border/80 bg-background/50 px-2 py-1 font-mono text-[10px] text-muted-foreground transition hover:border-terminal-green/50 hover:text-terminal-green disabled:opacity-40"
              >
                {s}
              </button>
            ))}
        <button
          type="button"
          disabled={isStreaming || loadingSuggestions}
          onClick={() =>
            loadSuggestions(recentQueriesRef.current, {
              force: true,
              useAi: true,
            })
          }
          title="AI 刷新推荐问题（较慢）"
          className="rounded border border-terminal-border/80 p-1 text-muted-foreground transition hover:border-terminal-green/50 hover:text-terminal-green disabled:opacity-40"
        >
          <RefreshCw
            className={cn("h-3 w-3", loadingSuggestions && "animate-spin")}
          />
        </button>
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
          disabled={!isStreaming && !value.trim()}
          onClick={handlePrimaryAction}
          title={isStreaming ? "停止生成" : "发送"}
          className={cn(
            "shrink-0",
            isStreaming && "border-terminal-amber/50 text-terminal-amber hover:bg-terminal-amber/10"
          )}
        >
          {isStreaming ? (
            <Square className="h-3.5 w-3.5 fill-current" />
          ) : (
            <ArrowUp className="h-4 w-4" />
          )}
        </Button>
      </div>
      <p className="mt-2 text-center font-mono text-[10px] text-muted-foreground/60">
        SSE 流式 · Supabase 向量检索 · DeepSeek · 输入「打开同花顺」等可启动本机金融软件
      </p>
    </div>
  );
}
