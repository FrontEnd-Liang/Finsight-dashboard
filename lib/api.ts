const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type SSEEvent =
  | { type: "thinking"; content: string }
  | { type: "token"; content: string }
  | { type: "done"; sources?: SourceRef[] }
  | { type: "error"; message: string };

export interface SourceRef {
  ticker?: string;
  source?: string;
  score?: number;
}

export async function* streamChat(
  query: string,
  sessionId: string,
  signal?: AbortSignal
): AsyncGenerator<SSEEvent> {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, session_id: sessionId }),
    signal,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed (${response.status})`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) continue;
      const jsonStr = trimmed.slice(5).trim();
      if (!jsonStr) continue;
      try {
        yield JSON.parse(jsonStr) as SSEEvent;
      } catch {
        /* skip malformed chunks */
      }
    }
  }
}

export async function fetchSuggestions(
  recentQueries: string[] = [],
  signal?: AbortSignal
): Promise<string[]> {
  const response = await fetch(`${API_BASE}/api/suggestions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ recent_queries: recentQueries, count: 4 }),
    signal,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Failed to load suggestions");
  }
  const data = (await response.json()) as { suggestions?: string[] };
  return data.suggestions ?? [];
}

export async function ingestDemoData(): Promise<{ ingested_nodes: number }> {
  const response = await fetch(`${API_BASE}/api/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ use_demo: true }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Ingest failed");
  }
  return response.json();
}

export async function resetSession(sessionId: string): Promise<void> {
  await fetch(`${API_BASE}/api/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
}
