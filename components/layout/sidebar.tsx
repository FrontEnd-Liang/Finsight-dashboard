"use client";

import { useState } from "react";
import {
  BarChart3,
  CheckCircle2,
  Database,
  Loader2,
  MessageSquarePlus,
  Trash2,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import type { CorpusStatus, IngestDemoResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface ChatSession {
  id: string;
  title: string;
  updatedAt: number;
}

interface SidebarProps {
  sessions: ChatSession[];
  activeSessionId: string;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
  /** 从 backend/data/demo_corpus.json 注入向量库 */
  onIngestDemo: () => Promise<IngestDemoResponse>;
  corpusStatus: CorpusStatus | null;
  onRefreshCorpusStatus?: () => void;
  isIngesting?: boolean;
}

export function Sidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  onIngestDemo,
  corpusStatus,
  onRefreshCorpusStatus,
  isIngesting = false,
}: SidebarProps) {
  const [ingestFeedback, setIngestFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  const handleIngestDemo = async () => {
    setIngestFeedback(null);
    try {
      const result = await onIngestDemo();
      const tickers = corpusStatus?.demo_tickers?.join(", ") ?? "演示标的";
      setIngestFeedback({
        type: "success",
        message: `已注入 ${result.ingested_nodes} 条（库内共 ${result.stored_count} 条）· ${tickers}`,
      });
      onRefreshCorpusStatus?.();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "语料导入失败，请检查后端与 Supabase";
      setIngestFeedback({ type: "error", message });
    }
  };

  const storedCount = corpusStatus?.stored_count ?? 0;
  const demoCount = corpusStatus?.demo_file_count ?? 0;
  const isLoaded = corpusStatus?.is_loaded ?? false;

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-terminal-border bg-terminal-panel">
      <div className="flex items-center gap-2 border-b border-terminal-border px-4 py-4">
        <div className="flex h-9 w-9 items-center justify-center rounded border border-terminal-green/50 bg-terminal-green/10">
          <TrendingUp className="h-5 w-5 text-terminal-green" />
        </div>
        <div>
          <h1 className="font-mono text-sm font-bold tracking-tight text-terminal-green">
            FINSIGHT
          </h1>
          <p className="font-mono text-[9px] text-muted-foreground">
            研究终端 v1.0
          </p>
        </div>
      </div>

      <div className="space-y-2 p-3">
        <Button
          variant="terminal"
          className="w-full justify-start gap-2"
          onClick={onNewSession}
        >
          <MessageSquarePlus className="h-4 w-4" />
          新建研究
        </Button>
        <Button
          variant="outline"
          className="w-full justify-start gap-2 border-terminal-border font-mono text-xs"
          onClick={handleIngestDemo}
          disabled={isIngesting}
          title="读取 backend/data/demo_corpus.json，向 Supabase 向量表写入演示财报"
        >
          {isIngesting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Database className="h-4 w-4" />
          )}
          {isIngesting ? "导入中…" : "加载演示语料库"}
        </Button>
        {ingestFeedback && (
          <p
            className={cn(
              "rounded border px-2 py-1.5 font-mono text-[9px] leading-relaxed",
              ingestFeedback.type === "success"
                ? "border-terminal-green/40 bg-terminal-green/5 text-terminal-green"
                : "border-terminal-red/40 bg-terminal-red/5 text-terminal-red"
            )}
          >
            {ingestFeedback.type === "success" && (
              <CheckCircle2 className="mb-0.5 mr-1 inline h-3 w-3" />
            )}
            {ingestFeedback.message}
          </p>
        )}
      </div>

      <Separator className="bg-terminal-border" />

      <div className="flex items-center gap-2 px-4 py-2">
        <BarChart3 className="h-3 w-3 text-terminal-amber" />
        <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          会话历史
        </span>
      </div>

      <ScrollArea className="flex-1 px-2">
        <div className="space-y-1 pb-4">
          {sessions.length === 0 && (
            <p className="px-2 py-4 font-mono text-[10px] text-muted-foreground">
              暂无会话
            </p>
          )}
          {sessions.map((session) => (
            <div
              key={session.id}
              className={cn(
                "group flex items-center gap-1 rounded-md border px-2 py-2 transition",
                activeSessionId === session.id
                  ? "border-terminal-green/40 bg-terminal-green/5"
                  : "border-transparent hover:border-terminal-border hover:bg-background/30"
              )}
            >
              <button
                type="button"
                onClick={() => onSelectSession(session.id)}
                className="min-w-0 flex-1 text-left"
              >
                <p className="truncate font-mono text-xs text-foreground">
                  {session.title}
                </p>
                <p className="font-mono text-[9px] text-muted-foreground">
                  {new Date(session.updatedAt).toLocaleString("zh-CN")}
                </p>
              </button>
              <button
                type="button"
                onClick={() => onDeleteSession(session.id)}
                className="opacity-0 transition group-hover:opacity-100 text-muted-foreground hover:text-terminal-red"
                aria-label="删除会话"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      </ScrollArea>

      <div className="border-t border-terminal-border p-3">
        <div className="rounded border border-terminal-border bg-background/40 p-2 font-mono text-[9px] leading-relaxed text-muted-foreground">
          <span className="text-terminal-green">语料库</span>
          {corpusStatus ? (
            <>
              {" "}
              · 已存{" "}
              <span
                className={
                  isLoaded ? "text-terminal-green" : "text-terminal-amber"
                }
              >
                {storedCount}
              </span>{" "}
              / 演示文件 {demoCount} 条
              <br />
              数据文件:{" "}
              <span className="text-foreground/80">
                backend/data/{corpusStatus.demo_file}
              </span>
              <br />
              标的: {corpusStatus.demo_tickers.join(" · ") || "—"}
              {corpusStatus.demo_as_of ? (
                <>
                  <br />
                  语料截至:{" "}
                  <span className="text-foreground/80">
                    {corpusStatus.demo_as_of}
                  </span>
                  {corpusStatus.demo_version
                    ? ` (v${corpusStatus.demo_version})`
                    : null}
                </>
              ) : null}
              {corpusStatus.needs_reload ? (
                <>
                  <br />
                  <span className="text-terminal-amber">
                    演示文件已更新，请重新加载语料
                  </span>
                </>
              ) : null}
            </>
          ) : (
            <>
              {" "}
              · <span className="text-terminal-amber">连接后端中…</span>
            </>
          )}
          <br />
          RAG: financial_documents
          <br />
          大模型: DeepSeek
        </div>
      </div>
    </aside>
  );
}
