"use client";

import {
  BarChart3,
  Database,
  MessageSquarePlus,
  Trash2,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
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
  onIngestDemo: () => void;
  isIngesting?: boolean;
}

export function Sidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  onIngestDemo,
  isIngesting,
}: SidebarProps) {
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
            RESEARCH TERMINAL v1.0
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
          New Research
        </Button>
        <Button
          variant="outline"
          className="w-full justify-start gap-2 border-terminal-border font-mono text-xs"
          onClick={onIngestDemo}
          disabled={isIngesting}
        >
          <Database className="h-4 w-4" />
          {isIngesting ? "Ingesting…" : "Load Demo Corpus"}
        </Button>
      </div>

      <Separator className="bg-terminal-border" />

      <div className="flex items-center gap-2 px-4 py-2">
        <BarChart3 className="h-3 w-3 text-terminal-amber" />
        <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          Session History
        </span>
      </div>

      <ScrollArea className="flex-1 px-2">
        <div className="space-y-1 pb-4">
          {sessions.length === 0 && (
            <p className="px-2 py-4 font-mono text-[10px] text-muted-foreground">
              No sessions yet
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
                  {new Date(session.updatedAt).toLocaleString()}
                </p>
              </button>
              <button
                type="button"
                onClick={() => onDeleteSession(session.id)}
                className="opacity-0 transition group-hover:opacity-100 text-muted-foreground hover:text-terminal-red"
                aria-label="Delete session"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      </ScrollArea>

      <div className="border-t border-terminal-border p-3">
        <div className="rounded border border-terminal-border bg-background/40 p-2 font-mono text-[9px] leading-relaxed text-muted-foreground">
          <span className="text-terminal-green">LIVE</span> · NYSE delayed
          <br />
          RAG: financial_documents
          <br />
          LLM: DeepSeek
        </div>
      </div>
    </aside>
  );
}
