"use client";

import { useState } from "react";
import {
  Bot,
  Brain,
  Copy,
  FileSearch,
  RefreshCw,
  Square,
  ThumbsDown,
  ThumbsUp,
  User,
  Volume2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { isSpeechSupported, speakText, stopSpeaking } from "@/lib/speech";
import { MarkdownMessage } from "./markdown-message";
import type { SourceRef } from "@/lib/api";
import type { ToastType } from "@/lib/use-toast";

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
  onRegenerate?: (messageId: string) => void;
  onNotify?: (message: string, type?: ToastType) => void;
  isRegenerating?: boolean;
  isSpeakingThis?: boolean;
  onSpeak?: (messageId: string) => void;
  onStopSpeak?: () => void;
}

function ActionBtn({
  label,
  onClick,
  disabled,
  active,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  active?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1 rounded border px-2 py-1 font-mono text-[9px] uppercase tracking-wide transition disabled:opacity-40",
        active
          ? "border-terminal-amber/50 bg-terminal-amber/10 text-terminal-amber"
          : "border-terminal-border text-muted-foreground hover:border-terminal-green/40 hover:text-terminal-green"
      )}
    >
      {children}
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}

export function ChatMessage({
  message,
  onFeedback,
  onRegenerate,
  onNotify,
  isRegenerating,
  isSpeakingThis,
  onSpeak,
  onStopSpeak,
}: ChatMessageProps) {
  const isUser = message.role === "user";
  const hasThinking =
    Boolean(message.thinking?.trim()) || Boolean(message.isThinking);
  const hasSources = Boolean(message.sources && message.sources.length > 0);
  const [thinkingOpen, setThinkingOpen] = useState(false);
  const [thinkingDialogOpen, setThinkingDialogOpen] = useState(false);
  const [sourcesDialogOpen, setSourcesDialogOpen] = useState(false);

  const showActions =
    !isUser && !message.isStreaming && Boolean(message.content?.trim());
  const showFeedback = showActions && onFeedback;

  const setFeedback = (next: MessageFeedback) => {
    if (!onFeedback) return;
    onFeedback(message.id, message.feedback === next ? null : next);
    if (next === "up") onNotify?.("已标记为有帮助", "success");
    else onNotify?.("已记录负反馈，将用于优化资料库", "info");
  };

  const handleCopy = async () => {
    const text = message.content?.trim();
    if (!text) {
      onNotify?.("暂无内容可复制", "error");
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      onNotify?.("回答已复制到剪贴板", "success");
    } catch {
      onNotify?.("复制失败，请手动选择文本", "error");
    }
  };

  const handleSpeak = () => {
    if (isSpeakingThis) {
      stopSpeaking();
      onStopSpeak?.();
      onNotify?.("已停止朗读", "info");
      return;
    }
    if (!isSpeechSupported()) {
      onNotify?.("当前浏览器不支持语音朗读", "error");
      return;
    }
    const text = message.content?.trim();
    if (!text) {
      onNotify?.("暂无内容可朗读", "error");
      return;
    }
    onSpeak?.(message.id);
    const ok = speakText(text, {
      onStart: () => onNotify?.("开始朗读回答", "info"),
      onEnd: () => onStopSpeak?.(),
      onError: () => {
        onStopSpeak?.();
        onNotify?.("朗读失败", "error");
      },
    });
    if (!ok) onNotify?.("无法启动朗读", "error");
  };

  const handleRegenerate = () => {
    if (!onRegenerate) return;
    onRegenerate(message.id);
    onNotify?.("正在重新生成回答…", "info");
  };

  const openThinking = () => {
    if (!hasThinking) {
      onNotify?.("本条回答暂无思考过程", "error");
      return;
    }
    setThinkingDialogOpen(true);
    onNotify?.("已打开思考过程", "info");
  };

  const openSources = () => {
    if (!hasSources) {
      onNotify?.("本条回答暂无引用来源", "error");
      return;
    }
    setSourcesDialogOpen(true);
    onNotify?.("已打开引用来源", "info");
  };

  return (
    <>
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
            <p className="text-sm leading-relaxed text-foreground">
              {message.content}
            </p>
          ) : (
            <>
              {hasThinking && (
                <div className="rounded border border-terminal-border/80 bg-terminal-panel/50">
                  <button
                    type="button"
                    onClick={() => setThinkingOpen((o) => !o)}
                    className="flex w-full items-center justify-between gap-2 px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-terminal-amber/90 hover:text-terminal-amber"
                  >
                    <span className="flex items-center gap-2">
                      <Brain className="h-3 w-3" />
                      思考过程（内联预览）
                    </span>
                    <span className="text-[9px] text-muted-foreground">
                      {thinkingOpen ? "收起" : "展开"}
                    </span>
                  </button>
                  {thinkingOpen && (
                    <div className="border-t border-terminal-border/60 px-3 py-2">
                      <MarkdownMessage
                        content={
                          message.thinking?.trim() ||
                          "正在检索资料库并规划分析路径…"
                        }
                        className="text-xs text-muted-foreground [&_p]:leading-relaxed"
                      />
                    </div>
                  )}
                </div>
              )}
              <MarkdownMessage content={message.content || " "} />
            </>
          )}

          {showActions && (
            <div className="flex flex-col gap-2 border-t border-terminal-border/50 pt-2">
              <div className="flex flex-wrap gap-1.5">
                <ActionBtn
                  label="重新生成"
                  onClick={handleRegenerate}
                  disabled={isRegenerating || !onRegenerate}
                >
                  <RefreshCw
                    className={cn(
                      "h-3 w-3",
                      isRegenerating && "animate-spin"
                    )}
                  />
                </ActionBtn>
                <ActionBtn label="复制回答" onClick={handleCopy}>
                  <Copy className="h-3 w-3" />
                </ActionBtn>
                <ActionBtn
                  label={isSpeakingThis ? "停止朗读" : "语音朗读"}
                  onClick={handleSpeak}
                  active={isSpeakingThis}
                >
                  {isSpeakingThis ? (
                    <Square className="h-3 w-3" />
                  ) : (
                    <Volume2 className="h-3 w-3" />
                  )}
                </ActionBtn>
                <ActionBtn label="思考过程" onClick={openThinking}>
                  <Brain className="h-3 w-3" />
                </ActionBtn>
                <ActionBtn label="引用来源" onClick={openSources}>
                  <FileSearch className="h-3 w-3" />
                </ActionBtn>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2">
                {hasSources ? (
                  <div className="flex flex-wrap gap-1.5">
                    {message.sources!.slice(0, 3).map((src, i) => (
                      <span
                        key={`${src.ticker}-${i}`}
                        className="rounded border border-terminal-border bg-terminal-panel px-2 py-0.5 font-mono text-[10px] text-terminal-green/80"
                      >
                        {src.ticker ?? "文档"} · {src.score?.toFixed(2)}
                      </span>
                    ))}
                    {message.sources!.length > 3 && (
                      <button
                        type="button"
                        onClick={openSources}
                        className="font-mono text-[9px] text-terminal-amber hover:underline"
                      >
                        +{message.sources!.length - 3} 条
                      </button>
                    )}
                  </div>
                ) : (
                  <span className="font-mono text-[9px] text-muted-foreground/60">
                    无引用来源
                  </span>
                )}
                {showFeedback && (
                  <div className="flex items-center gap-1">
                    <span className="mr-1 font-mono text-[9px] text-muted-foreground/70">
                      有帮助吗？
                    </span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className={cn(
                        "h-7 w-7",
                        message.feedback === "up" &&
                          "text-terminal-green"
                      )}
                      onClick={() => setFeedback("up")}
                      aria-label="有帮助"
                    >
                      <ThumbsUp className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className={cn(
                        "h-7 w-7",
                        message.feedback === "down" &&
                          "text-terminal-red"
                      )}
                      onClick={() => setFeedback("down")}
                      aria-label="无帮助"
                    >
                      <ThumbsDown className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      <Dialog open={thinkingDialogOpen} onOpenChange={setThinkingDialogOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>思考过程</DialogTitle>
            <DialogDescription>
              检索资料库命中与回答前的分析摘要
            </DialogDescription>
          </DialogHeader>
          <MarkdownMessage
            content={message.thinking?.trim() || "（无内容）"}
            className="text-sm text-muted-foreground"
          />
        </DialogContent>
      </Dialog>

      <Dialog open={sourcesDialogOpen} onOpenChange={setSourcesDialogOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>引用来源</DialogTitle>
            <DialogDescription>
              RAG 检索命中的资料片段（相似度越高越相关）
            </DialogDescription>
          </DialogHeader>
          <ul className="space-y-3">
            {(message.sources ?? []).map((src, i) => (
              <li
                key={`${src.ticker}-${src.source}-${i}`}
                className="rounded border border-terminal-border bg-background/40 px-3 py-2"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 font-mono text-xs">
                  <span className="text-terminal-green">
                    {src.ticker ?? "—"}
                  </span>
                  <span className="text-terminal-amber">
                    相似度 {(src.score ?? 0).toFixed(4)}
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {src.source ?? "未知来源"}
                </p>
              </li>
            ))}
          </ul>
        </DialogContent>
      </Dialog>
    </>
  );
}
