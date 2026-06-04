"use client";

import { Bot, User } from "lucide-react";
import { cn } from "@/lib/utils";
import { MarkdownMessage } from "./markdown-message";
import type { SourceRef } from "@/lib/api";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceRef[];
  isStreaming?: boolean;
}

interface ChatMessageProps {
  message: Message;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";

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
          {isUser ? "Analyst Query" : "Finsight Agent"}
          {message.isStreaming && (
            <span className="ml-2 inline-block h-3 w-1.5 animate-blink bg-terminal-green" />
          )}
        </div>
        {isUser ? (
          <p className="text-sm leading-relaxed text-foreground">{message.content}</p>
        ) : (
          <MarkdownMessage content={message.content || " "} />
        )}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-1">
            {message.sources.map((src, i) => (
              <span
                key={`${src.ticker}-${i}`}
                className="rounded border border-terminal-border bg-terminal-panel px-2 py-0.5 font-mono text-[10px] text-terminal-green/80"
              >
                {src.ticker ?? "DOC"} · {src.source ?? "source"} ·{" "}
                {src.score?.toFixed(2)}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
