const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const LAUNCH_VERBS = ["打开", "启动", "运行", "开启", "launch", "open", "start"];

export interface LaunchAppResult {
  matched: boolean;
  launched?: boolean;
  app_id?: string;
  app_name?: string;
  message?: string;
  installed_apps?: string[];
}

export function isLaunchIntent(query: string): boolean {
  const text = query.trim();
  if (!text) return false;
  const verbPattern = LAUNCH_VERBS.join("|");
  return new RegExp(`^(${verbPattern})\\s*.+`, "i").test(text);
}

export async function launchFinancialApp(query: string): Promise<LaunchAppResult> {
  const response = await fetch(`${API_BASE}/api/launch-app`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Launch failed (${response.status})`);
  }
  return response.json() as Promise<LaunchAppResult>;
}
