"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Activity, AlertCircle } from "lucide-react";
import { ChatInput } from "@/components/chat/chat-input";
import {
  ChatMessage,
  type Message,
  type MessageFeedback,
} from "@/components/chat/chat-message";
import { Sidebar, type ChatSession } from "@/components/layout/sidebar";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ToastStack } from "@/components/ui/toast-stack";
import {
  fetchCorpusStatus,
  clearFeedback,
  ingestLibraryData,
  resetSession,
  streamChat,
  submitFeedback,
  type CorpusStatus,
} from "@/lib/api";
import { stopSpeaking } from "@/lib/speech";
import {
  createSessionId,
  deleteSessionCaches,
  loadMessages,
  loadSessions,
  saveMessages,
  saveSessions,
  titleFromQuery,
} from "@/lib/sessions";
import { isLaunchIntent, launchFinancialApp } from "@/lib/launch-app";
import { useToast } from "@/lib/use-toast";

export default function HomePage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);
  const [regeneratingId, setRegeneratingId] = useState<string | null>(null);
  const [speakingMessageId, setSpeakingMessageId] = useState<string | null>(
    null
  );
  const [error, setError] = useState<string | null>(null);
  const [statusLine, setStatusLine] = useState("就绪");
  const [suggestionRefreshKey, setSuggestionRefreshKey] = useState(0);
  const [corpusStatus, setCorpusStatus] = useState<CorpusStatus | null>(null);
  const { toasts, notify, dismiss } = useToast();
  const abortRef = useRef<AbortController | null>(null);

  const refreshCorpusStatus = useCallback(async () => {
    try {
      const status = await fetchCorpusStatus();
      setCorpusStatus(status);
    } catch {
      setCorpusStatus(null);
    }
  }, []);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    refreshCorpusStatus();
  }, [refreshCorpusStatus]);

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

  useEffect(() => {
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.getVoices();
    }
    return () => stopSpeaking();
  }, []);

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

  const runAssistantStream = useCallback(
    async (query: string, assistantId: string, sessionId: string) => {
      abortRef.current?.abort();
      abortRef.current = new AbortController();
      setIsStreaming(true);
      setError(null);
      setStatusLine("准备分析…");

      try {
        let accumulated = "";
        let thinkingAccum = "";

        for await (const event of streamChat(
          query,
          sessionId,
          abortRef.current.signal
        )) {
          if (event.type === "thinking_step") {
            setStatusLine(event.label);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      thinkingStep: event.label,
                      isThinking: true,
                      isStreaming: true,
                    }
                  : m
              )
            );
          } else if (event.type === "thinking") {
            thinkingAccum += event.content;
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
            if (event.content === "Empty Response") continue;
            accumulated += event.content;
            setStatusLine("生成回答…");
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      content: accumulated,
                      isThinking: false,
                      thinkingStep: undefined,
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
                      thinkingStep: undefined,
                      sources: event.sources,
                      isStreaming: false,
                      isThinking: false,
                      feedback: undefined,
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
          notify("已停止生成", "info");
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
        notify(message, "error");
      } finally {
        setIsStreaming(false);
        setRegeneratingId(null);
      }
    },
    [notify]
  );

  const handleSend = async (query: string) => {
    if (!activeSessionId || isStreaming) return;

    const userMessage: Message = {
      id: `msg_${Date.now()}_user`,
      role: "user",
      content: query,
    };

    if (isLaunchIntent(query)) {
      const assistantId = `msg_${Date.now()}_assistant`;
      setMessages((prev) => [
        ...prev,
        userMessage,
        {
          id: assistantId,
          role: "assistant",
          content: "正在检测本机金融软件…",
          thinking: "",
          isStreaming: false,
          isThinking: false,
        },
      ]);
      updateSessionTitle(activeSessionId, query);

      try {
        const result = await launchFinancialApp(query);
        const message =
          result.message ??
          (result.launched ? "已启动金融软件。" : "未能启动金融软件。");

        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: message } : m
          )
        );
        notify(message, result.launched ? "success" : "error");
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "启动金融软件失败，请检查后端服务";
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: message } : m
          )
        );
        notify(message, "error");
      }
      return;
    }

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
    await runAssistantStream(query, assistantId, activeSessionId);
  };

  const handleRegenerate = useCallback(
    async (assistantMessageId: string) => {
      if (!activeSessionId || isStreaming) {
        notify("请等待当前回答完成", "error");
        return;
      }

      const idx = messages.findIndex((m) => m.id === assistantMessageId);
      if (idx < 1) {
        notify("无法找到对应提问", "error");
        return;
      }

      const userMsg = messages[idx - 1];
      if (userMsg.role !== "user") {
        notify("无法找到对应提问", "error");
        return;
      }

      const query = userMsg.content;
      const newAssistantId = `msg_${Date.now()}_assistant`;

      stopSpeaking();
      setSpeakingMessageId(null);

      if (activeSessionId) {
        try {
          await clearFeedback(activeSessionId, assistantMessageId);
        } catch {
          /* ignore */
        }
      }

      setRegeneratingId(newAssistantId);
      setMessages((prev) => {
        const at = prev.findIndex((m) => m.id === assistantMessageId);
        const before = prev.slice(0, at);
        return [
          ...before,
          {
            id: newAssistantId,
            role: "assistant",
            content: "",
            thinking: "",
            isStreaming: true,
            isThinking: true,
          },
        ];
      });

      await runAssistantStream(query, newAssistantId, activeSessionId);
    },
    [activeSessionId, isStreaming, messages, notify, runAssistantStream]
  );

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
    notify("正在停止…", "info");
  }, [notify]);

  const handleMessageFeedback = useCallback(
    async (messageId: string, feedback: MessageFeedback | null) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId
            ? { ...m, feedback: feedback ?? undefined }
            : m
        )
      );

      if (!activeSessionId) return;

      const idx = messages.findIndex((m) => m.id === messageId);
      const assistant = messages[idx];
      if (!assistant || assistant.role !== "assistant") return;

      const userMsg = idx > 0 ? messages[idx - 1] : null;
      const userQuery =
        userMsg?.role === "user" ? userMsg.content : "（未找到对应提问）";

      try {
        if (feedback === "down") {
          await submitFeedback({
            session_id: activeSessionId,
            message_id: messageId,
            feedback: "down",
            user_query: userQuery,
            assistant_content: assistant.content,
            thinking: assistant.thinking,
            sources: assistant.sources,
          });
          setStatusLine("已记录反馈");
        } else if (feedback === "up") {
          await submitFeedback({
            session_id: activeSessionId,
            message_id: messageId,
            feedback: "up",
            user_query: userQuery,
            assistant_content: assistant.content,
            thinking: assistant.thinking,
            sources: assistant.sources,
          });
        } else {
          await clearFeedback(activeSessionId, messageId);
          notify("已取消反馈", "info");
          return;
        }
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "反馈提交失败";
        setError(message);
        notify(message, "error");
      }
    },
    [activeSessionId, messages, notify]
  );

  const handleNewSession = () => {
    abortRef.current?.abort();
    stopSpeaking();
    setSpeakingMessageId(null);
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
    notify("已新建研究会话", "success");
  };

  const switchToSession = useCallback((id: string) => {
    stopSpeaking();
    setSpeakingMessageId(null);
    setActiveSessionId(id);
    setMessages(loadMessages(id));
    setError(null);
    setStatusLine("就绪");
  }, []);

  const handleSelectSession = (id: string) => {
    abortRef.current?.abort();
    switchToSession(id);
  };

  const createFreshSession = useCallback((): ChatSession => {
    const fresh: ChatSession = {
      id: createSessionId(),
      title: "新建研究",
      updatedAt: Date.now(),
    };
    saveSessions([fresh]);
    switchToSession(fresh.id);
    setSessions([fresh]);
    return fresh;
  }, [switchToSession]);

  const handleDeleteSession = async (id: string) => {
    const target = sessions.find((s) => s.id === id);
    const label = target?.title?.trim() || "未命名会话";
    if (!window.confirm(`确定删除「${label}」？对话记录将永久移除，且不可恢复。`)) {
      return;
    }

    if (activeSessionId === id) {
      abortRef.current?.abort();
      setIsStreaming(false);
      stopSpeaking();
      setSpeakingMessageId(null);
    }

    deleteSessionCaches(id);
    try {
      await resetSession(id);
    } catch {
      /* backend reset is best-effort */
    }

    const next = sessions.filter((s) => s.id !== id);
    if (next.length === 0) {
      createFreshSession();
      notify("会话已删除，已创建新会话", "info");
      return;
    }

    saveSessions(next);
    setSessions(next);
    if (activeSessionId === id) {
      switchToSession(next[0].id);
    }
    notify("会话已删除", "success");
  };

  const handleClearAllSessions = async () => {
    if (sessions.length === 0) return;
    if (
      !window.confirm(
        `确定清空全部 ${sessions.length} 条会话历史？所有对话记录将永久移除，且不可恢复。`
      )
    ) {
      return;
    }

    abortRef.current?.abort();
    setIsStreaming(false);
    stopSpeaking();
    setSpeakingMessageId(null);

    await Promise.all(
      sessions.map(async (s) => {
        deleteSessionCaches(s.id);
        try {
          await resetSession(s.id);
        } catch {
          /* best-effort */
        }
      })
    );

    createFreshSession();
    notify("已清空全部会话历史", "success");
  };

  const handleSyncLibrary = async () => {
    setIsIngesting(true);
    setError(null);
    setStatusLine("同步资料库…");
    notify("正在同步资料库…", "info");
    try {
      const result = await ingestLibraryData(true);
      setSuggestionRefreshKey((k) => k + 1);
      await refreshCorpusStatus();
      setStatusLine(
        `已导入 ${result.ingested_nodes} 条（向量库共 ${result.stored_count} 条）`
      );
      notify(
        `资料库已同步：${result.ingested_nodes} 条文档`,
        "success"
      );
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : "导入失败";
      setError(message);
      setStatusLine("导入错误");
      notify(message, "error");
      throw err;
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
        onClearAllSessions={handleClearAllSessions}
        onSyncLibrary={handleSyncLibrary}
        corpusStatus={corpusStatus}
        onRefreshCorpusStatus={refreshCorpusStatus}
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
                  请先从侧边栏同步资料库，随后可提问跨品种权益或宏观类问题。
                  回答将先展示思考过程（检索命中与内部分析规划），再流式输出正文，并附带引用来源。
                </p>
              </div>
            )}
            {messages.map((message) => (
              <ChatMessage
                key={message.id}
                message={message}
                onFeedback={handleMessageFeedback}
                onRegenerate={handleRegenerate}
                onNotify={notify}
                isRegenerating={
                  regeneratingId === message.id && message.isStreaming
                }
                isSpeakingThis={speakingMessageId === message.id}
                onSpeak={(id) => setSpeakingMessageId(id)}
                onStopSpeak={() => setSpeakingMessageId(null)}
              />
            ))}
            <div ref={bottomRef} />
          </div>
        </ScrollArea>

        <ChatInput
          onSend={handleSend}
          isStreaming={isStreaming}
          onStop={handleStop}
          sessionId={activeSessionId || "default"}
          refreshKey={suggestionRefreshKey}
          recentQueries={messages
            .filter((m) => m.role === "user")
            .map((m) => m.content)
            .slice(-3)}
        />
      </main>

      <ToastStack toasts={toasts} onDismiss={dismiss} />
    </div>
  );
}
