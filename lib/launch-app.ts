const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const LAUNCH_VERBS = ["打开", "启动", "运行", "开启", "launch", "open", "start"];
const LOGIN_VERBS = ["登录", "登陆", "登入", "login", "sign in", "signin"];
const APP_KEYWORDS = [
  "东方财富",
  "东财",
  "同花顺",
  "通达信",
  "wind",
  "万得",
  "choice",
  "大智慧",
  "金融软件",
  "炒股软件",
];

export interface LaunchAppResult {
  matched: boolean;
  launched?: boolean;
  app_id?: string;
  app_name?: string;
  message?: string;
  installed_apps?: string[];
  intent?: {
    launch?: boolean;
    login?: boolean;
    phone_masked?: string | null;
    login_method?: string;
    clipboard_ready?: boolean;
  };
}

export function isLaunchIntent(query: string): boolean {
  const text = query.trim();
  if (!text) return false;

  const verbPattern = LAUNCH_VERBS.join("|");
  if (new RegExp(`^(${verbPattern})\\s*.+`, "i").test(text)) {
    return true;
  }

  const hasLogin = LOGIN_VERBS.some((verb) => text.includes(verb));
  const hasPhone = /1[3-9]\d{9}/.test(text);
  const hasApp = APP_KEYWORDS.some((keyword) =>
    text.toLowerCase().includes(keyword.toLowerCase())
  );
  if (hasLogin && hasPhone && hasApp) {
    return true;
  }

  const hasNavigate = /(切换到|切到|进入|打开|查看).*(大盘|行情|自选|上证|深证)/.test(
    text
  );
  return hasApp && hasNavigate;
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
