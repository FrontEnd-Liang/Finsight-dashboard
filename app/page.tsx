"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Activity, AlertCircle } from "lucide-react";
import { ChatInput } from "@/components/chat/chat-input";
import { ChatMessage, type Message } from "@/components/chat/chat-message";
import { Sidebar, type ChatSession } from "@/components/layout/sidebar";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ingestDemoData, resetSession, streamChat } from "@/lib/api";
import {
  createSessionId,
  deleteMessages,
  loadMessages,
  loadSessions,
  saveMessages,
  saveSessions,
  titleFromQuery,
} from "@/lib/sessions";

export default function HomePage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusLine, setStatusLine] = useState("就绪");
  const [suggestionRefreshKey, setSuggestionRefreshKey] = useState(0);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const stored = loadSessions();
    if (stored.length > 0) {
      setSessions(stored);
      setActiveSessionId(stored[0].id);
      setMessages(loadMessages(stored[0].id));
    } else {
      const id = createSessionId();
      const initial: ChatSession = {
        id,
        title: "新建研究",
        updatedAt: Date.now(),
      };
      setSessions([initial]);
      setActiveSessionId(id);
      saveSessions([initial]);
    }
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!activeSessionId) return;
    saveMessages(activeSessionId, messages);
  }, [messages, activeSessionId]);

  const updateSessionTitle = useCallback(
    (sessionId: string, query: string) => {
      setSessions((prev) => {
        const next = prev.map((s) =>
          s.id === sessionId && s.title === "新建研究"
            ? { ...s, title: titleFromQuery(query), updatedAt: Date.now() }
            : s.id === sessionId
              ? { ...s, updatedAt: Date.now() }
              : s
        );
        saveSessions(next);
        return next;
      });
    },
    []
  );

  const handleSend = async (query: string) => {
    if (!activeSessionId || isStreaming) return;

    setError(null);
    setStatusLine("检索上下文…");

    const userMessage: Message = {
      id: `msg_${Date.now()}_user`,
      role: "user",
      content: query,
    };

    const assistantId = `msg_${Date.now()}_assistant`;
    const assistantMessage: Message = {
      id: assistantId,
      role: "assistant",
      content: "",
      thinking: "",
      isStreaming: true,
      isThinking: true,
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    updateSessionTitle(activeSessionId, query);
    setIsStreaming(true);

    abortRef.current?.abort();
    abortRef.current = new AbortController();

    try {
      setStatusLine("流式响应中…");
      let accumulated = "";
      let thinkingAccum = "";

      for await (const event of streamChat(
        query,
        activeSessionId,
        abortRef.current.signal
      )) {
        if (event.type === "thinking") {
          thinkingAccum += event.content;
          setStatusLine("思考中…");
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    thinking: thinkingAccum,
                    isThinking: true,
                    isStreaming: true,
                  }
                : m
            )
          );
        } else if (event.type === "token") {
          accumulated += event.content;
          setStatusLine("生成回答…");
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    content: accumulated,
                    isThinking: false,
                    isStreaming: true,
                  }
                : m
            )
          );
        } else if (event.type === "done") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    content: accumulated,
                    thinking: thinkingAccum || undefined,
                    sources: event.sources,
                    isStreaming: false,
                    isThinking: false,
                  }
                : m
            )
          );
          setStatusLine("就绪");
        } else if (event.type === "error") {
          throw new Error(event.message);
        }
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        setStatusLine("已停止");
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  isStreaming: false,
                  isThinking: false,
                  content:
                    m.content?.trim() ||
                    m.thinking?.trim() ||
                    "（已停止生成）",
                }
              : m
          )
        );
        return;
      }
      const message = err instanceof Error ? err.message : "流式传输失败";
      setError(message);
      setStatusLine("错误");
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
                ? {
                ...m,
                content: `**错误：** ${message}`,
                isStreaming: false,
                isThinking: false,
              }
            : m
        )
      );
    } finally {
      setIsStreaming(false);
    }
  };

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const handleNewSession = () => {
    abortRef.current?.abort();
    const id = createSessionId();
    const session: ChatSession = {
      id,
      title: "新建研究",
      updatedAt: Date.now(),
    };
    setSessions((prev) => {
      const next = [session, ...prev];
      saveSessions(next);
      return next;
    });
    setActiveSessionId(id);
    setMessages([]);
    setError(null);
    setStatusLine("就绪");
  };

  const handleSelectSession = (id: string) => {
    abortRef.current?.abort();
    setActiveSessionId(id);
    setMessages(loadMessages(id));
    setError(null);
    setStatusLine("就绪");
  };

  const handleDeleteSession = async (id: string) => {
    deleteMessages(id);
    try {
      await resetSession(id);
    } catch {
      /* backend reset is best-effort */
    }
    setSessions((prev) => {
      const next = prev.filter((s) => s.id !== id);
      saveSessions(next);
      if (activeSessionId === id) {
        if (next.length === 0) {
          const newId = createSessionId();
          const fresh: ChatSession = {
            id: newId,
            title: "新建研究",
            updatedAt: Date.now(),
          };
          saveSessions([fresh]);
          setActiveSessionId(newId);
          setMessages([]);
          return [fresh];
        }
        setActiveSessionId(next[0].id);
        setMessages(loadMessages(next[0].id));
      }
      return next;
    });
  };

  const handleIngestDemo = async () => {
    setIsIngesting(true);
    setError(null);
    setStatusLine("导入演示语料库…");
    try {
      const result = await ingestDemoData();
      setSuggestionRefreshKey((k) => k + 1);
      setStatusLine(`已导入 ${result.ingested_nodes} 份文档`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "导入失败";
      setError(message);
      setStatusLine("导入错误");
    } finally {
      setIsIngesting(false);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
        onIngestDemo={handleIngestDemo}
        isIngesting={isIngesting}
      />

      <main className="flex min-w-0 flex-1 flex-col terminal-grid">
        <header className="flex items-center justify-between border-b border-terminal-border bg-terminal-panel/60 px-4 py-3 backdrop-blur-sm">
          <div className="flex items-center gap-3">
            <Activity className="h-4 w-4 text-terminal-green animate-pulse-slow" />
            <span className="font-mono text-xs text-terminal-green">
              金融研究智能体
            </span>
            <span className="hidden font-mono text-[10px] text-muted-foreground sm:inline">
              · LlamaIndex RAG · Supabase 向量库
            </span>
          </div>
          <div className="flex items-center gap-4 font-mono text-[10px]">
            {error && (
              <span className="flex items-center gap-1 text-terminal-red">
                <AlertCircle className="h-3 w-3" />
                {error.slice(0, 60)}
              </span>
            )}
            <span className="text-terminal-amber">{statusLine}</span>
          </div>
        </header>

        <ScrollArea className="flex-1">
          <div className="mx-auto max-w-3xl">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center px-6 py-24 text-center">
                <h2 className="font-mono text-lg text-terminal-green">
                  欢迎使用 Finsight 终端
                </h2>
                <p className="mt-3 max-w-md text-sm text-muted-foreground">
                  请先从侧边栏加载演示语料库，随后可提问跨品种权益或宏观类问题。
                  回答将先展示思考过程（检索命中与内部分析规划），再流式输出正文，并附带引用来源。
                </p>
              </div>
            )}
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            <div ref={bottomRef} />
          </div>
        </ScrollArea>

        <ChatInput
          onSend={handleSend}
          isStreaming={isStreaming}
          onStop={handleStop}
          refreshKey={suggestionRefreshKey}
          recentQueries={messages
            .filter((m) => m.role === "user")
            .map((m) => m.content)
            .slice(-3)}
        />
      </main>
    </div>
  );
}
