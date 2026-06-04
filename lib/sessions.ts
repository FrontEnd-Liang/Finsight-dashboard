import type { Message } from "@/components/chat/chat-message";
import type { ChatSession } from "@/components/layout/sidebar";

const SESSIONS_KEY = "finsight_sessions";
const MESSAGES_PREFIX = "finsight_messages_";

export function loadSessions(): ChatSession[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(SESSIONS_KEY);
    return raw ? (JSON.parse(raw) as ChatSession[]) : [];
  } catch {
    return [];
  }
}

export function saveSessions(sessions: ChatSession[]): void {
  localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
}

export function loadMessages(sessionId: string): Message[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(`${MESSAGES_PREFIX}${sessionId}`);
    return raw ? (JSON.parse(raw) as Message[]) : [];
  } catch {
    return [];
  }
}

export function saveMessages(sessionId: string, messages: Message[]): void {
  localStorage.setItem(
    `${MESSAGES_PREFIX}${sessionId}`,
    JSON.stringify(messages)
  );
}

export function deleteMessages(sessionId: string): void {
  localStorage.removeItem(`${MESSAGES_PREFIX}${sessionId}`);
}

const SUGGESTIONS_CACHE_PREFIX = "finsight_suggestions_v2_";

/** Remove messages and per-session suggestion cache for a deleted session. */
export function deleteSessionCaches(sessionId: string): void {
  deleteMessages(sessionId);
  if (typeof window === "undefined") return;
  const prefix = `${SUGGESTIONS_CACHE_PREFIX}${sessionId}_`;
  for (let i = localStorage.length - 1; i >= 0; i--) {
    const key = localStorage.key(i);
    if (key?.startsWith(prefix)) {
      localStorage.removeItem(key);
    }
  }
}

export function createSessionId(): string {
  return `sess_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

export function titleFromQuery(query: string): string {
  const trimmed = query.trim();
  return trimmed.length > 42 ? `${trimmed.slice(0, 42)}…` : trimmed;
}
