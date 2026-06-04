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
  options: {
    recentQueries?: string[];
    useAi?: boolean;
    signal?: AbortSignal;
  } = {}
): Promise<string[]> {
  const { recentQueries = [], useAi = false, signal } = options;

  if (!useAi) {
    const response = await fetch(`${API_BASE}/api/suggestions?count=4`, {
      method: "GET",
      signal,
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || "Failed to load suggestions");
    }
    const data = (await response.json()) as { suggestions?: string[] };
    return data.suggestions ?? [];
  }

  const response = await fetch(`${API_BASE}/api/suggestions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      recent_queries: recentQueries,
      count: 4,
      use_ai: true,
    }),
    signal,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Failed to load suggestions");
  }
  const data = (await response.json()) as { suggestions?: string[] };
  return data.suggestions ?? [];
}

export interface CorpusStatus {
  stored_count: number;
  demo_file_count: number;
  demo_tickers: string[];
  demo_file: string;
  is_loaded: boolean;
}

export interface IngestDemoResponse {
  ingested_nodes: number;
  stored_count: number;
  status: string;
  replaced?: boolean;
}

export async function fetchCorpusStatus(): Promise<CorpusStatus> {
  const response = await fetch(`${API_BASE}/api/corpus/status`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Failed to fetch corpus status");
  }
  return response.json();
}

export async function ingestDemoData(
  replace = true
): Promise<IngestDemoResponse> {
  const response = await fetch(`${API_BASE}/api/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ use_demo: true, replace }),
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
