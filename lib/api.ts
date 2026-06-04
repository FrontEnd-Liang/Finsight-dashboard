const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type SSEEvent =
  | { type: "thinking"; content: string }
  | { type: "token"; content: string }
  | { type: "done"; sources?: SourceRef[] }
  | { type: "error"; message: string };

export interface SourceRef {
  rank?: number;
  ticker?: string;
  source?: string;
  score?: number;
  relevance?: string;
  sector?: string;
  doc_type?: string;
  fiscal_year?: number;
  fiscal_quarter?: string;
  period_end?: string;
  filed_date?: string;
  is_latest?: boolean;
  document_id?: string;
  excerpt?: string;
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
  library_manifest_count: number;
  library_tickers: string[];
  library_file: string;
  library_version?: string | null;
  library_as_of?: string | null;
  is_loaded: boolean;
  needs_reload?: boolean;
}

export interface IngestLibraryResponse {
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

export async function ingestLibraryData(
  replace = true
): Promise<IngestLibraryResponse> {
  const response = await fetch(`${API_BASE}/api/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ use_library: true, replace }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Ingest failed");
  }
  return response.json();
}

export interface FeedbackPayload {
  session_id: string;
  message_id: string;
  feedback: "up" | "down";
  user_query: string;
  assistant_content: string;
  thinking?: string;
  sources?: SourceRef[];
}

export async function submitFeedback(
  payload: FeedbackPayload
): Promise<{ status: string; queued_for_refinement?: boolean }> {
  const response = await fetch(`${API_BASE}/api/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Failed to submit feedback");
  }
  return response.json();
}

export async function clearFeedback(
  sessionId: string,
  messageId: string
): Promise<void> {
  const response = await fetch(
    `${API_BASE}/api/feedback/${encodeURIComponent(sessionId)}/${encodeURIComponent(messageId)}`,
    { method: "DELETE" }
  );
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Failed to clear feedback");
  }
}

export async function resetSession(sessionId: string): Promise<void> {
  await fetch(`${API_BASE}/api/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
}
