"use client";

import { useState } from "react";
import { Bot, ChevronDown, ChevronRight, ThumbsDown, ThumbsUp, User } from "lucide-react";
import { cn } from "@/lib/utils";
import { MarkdownMessage } from "./markdown-message";
import type { SourceRef } from "@/lib/api";

export type MessageFeedback = "up" | "down";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  thinking?: string;
  sources?: SourceRef[];
  feedback?: MessageFeedback;
  isStreaming?: boolean;
  isThinking?: boolean;
}

interface ChatMessageProps {
  message: Message;
  onFeedback?: (messageId: string, feedback: MessageFeedback | null) => void;
}

export function ChatMessage({ message, onFeedback }: ChatMessageProps) {
  const isUser = message.role === "user";
  const hasThinking =
    Boolean(message.thinking?.trim()) || Boolean(message.isThinking);
  const [thinkingOpen, setThinkingOpen] = useState(true);
  const showFeedback =
    !isUser &&
    !message.isStreaming &&
    Boolean(message.content?.trim()) &&
    onFeedback;

  const setFeedback = (next: MessageFeedback) => {
    if (!onFeedback) return;
    onFeedback(message.id, message.feedback === next ? null : next);
  };

  return (
    <div
      className={cn(
        "flex gap-3 px-4 py-4",
        isUser ? "bg-terminal-panel/30" : "bg-transparent"
      )}
    >
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded border",
          isUser
            ? "border-terminal-amber/40 text-terminal-amber"
            : "border-terminal-green/40 text-terminal-green"
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div className="min-w-0 flex-1 space-y-2">
        <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          {isUser ? "分析师提问" : "Finsight 智能体"}
          {message.isStreaming && (
            <span className="ml-2 inline-block h-3 w-1.5 animate-blink bg-terminal-green" />
          )}
        </div>
        {isUser ? (
          <p className="text-sm leading-relaxed text-foreground">{message.content}</p>
        ) : (
          <>
            {hasThinking && (
              <div className="rounded border border-terminal-border/80 bg-terminal-panel/50">
                <button
                  type="button"
                  onClick={() => setThinkingOpen((o) => !o)}
                  className="flex w-full items-center gap-2 px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-terminal-amber/90 hover:text-terminal-amber"
                >
                  {thinkingOpen ? (
                    <ChevronDown className="h-3 w-3 shrink-0" />
                  ) : (
                    <ChevronRight className="h-3 w-3 shrink-0" />
                  )}
                  思考过程
                  {message.isThinking && (
                    <span className="inline-block h-3 w-1.5 animate-blink bg-terminal-amber" />
                  )}
                </button>
                {thinkingOpen && (
                  <div className="border-t border-terminal-border/60 px-3 py-2">
                    <MarkdownMessage
                      content={message.thinking?.trim() || "正在检索资料库并规划分析路径…"}
                      className="text-xs text-muted-foreground [&_p]:leading-relaxed"
                    />
                  </div>
                )}
              </div>
            )}
            <MarkdownMessage content={message.content || " "} />
          </>
        )}
        {!isUser && (showFeedback || (message.sources && message.sources.length > 0)) && (
          <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
            {message.sources && message.sources.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {message.sources.map((src, i) => (
                  <span
                    key={`${src.ticker}-${i}`}
                    className="rounded border border-terminal-border bg-terminal-panel px-2 py-0.5 font-mono text-[10px] text-terminal-green/80"
                  >
                    {src.ticker ?? "文档"} · {src.source ?? "来源"} ·{" "}
                    {src.score?.toFixed(2)}
                  </span>
                ))}
              </div>
            ) : (
              <span />
            )}
            {showFeedback && (
              <div className="flex items-center gap-1">
                <span className="mr-1 font-mono text-[9px] text-muted-foreground/70">
                  这条回答有帮助吗？
                </span>
                <button
                  type="button"
                  onClick={() => setFeedback("up")}
                  aria-label="有帮助"
                  aria-pressed={message.feedback === "up"}
                  className={cn(
                    "rounded border p-1 transition",
                    message.feedback === "up"
                      ? "border-terminal-green/60 bg-terminal-green/15 text-terminal-green"
                      : "border-terminal-border text-muted-foreground hover:border-terminal-green/40 hover:text-terminal-green"
                  )}
                >
                  <ThumbsUp className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => setFeedback("down")}
                  aria-label="无帮助"
                  aria-pressed={message.feedback === "down"}
                  className={cn(
                    "rounded border p-1 transition",
                    message.feedback === "down"
                      ? "border-terminal-red/60 bg-terminal-red/15 text-terminal-red"
                      : "border-terminal-border text-muted-foreground hover:border-terminal-red/40 hover:text-terminal-red"
                  )}
                >
                  <ThumbsDown className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
