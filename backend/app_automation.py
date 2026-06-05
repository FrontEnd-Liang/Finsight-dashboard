"""Windows UI automation helpers for financial desktop apps."""

from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass, field

NAVIGATION_TARGETS: dict[str, tuple[str, ...]] = {
    "大盘": ("大盘", "大盘行情", "大盘一览", "大盘一栏", "市场大盘"),
    "上证指数": ("上证指数", "上证", "沪指"),
    "深证成指": ("深证成指", "深证", "深指"),
    "自选股": ("自选股", "自选"),
    "行情": ("行情", "行情报价", "报价"),
}

NAVIGATION_SHORTCUTS: dict[str, str] = {
    "上证指数": "{F3}",
    "深证成指": "{F4}",
    "自选股": "{F6}",
    "行情": "{F2}",
}

# 经典版左侧导航顺序（自上而下，与客户端侧栏一致）
EASTMONEY_SIDEBAR_MENU: tuple[str, ...] = (
    "全景",
    "自选",
    "沪深京",
    "板块",
    "大盘",
    "资讯",
    "数据",
    "新股",
)

# 相对窗口宽高的比例定位，适配不同分辨率 / 缩放
EASTMONEY_SIDEBAR_X_RATIO = 0.012
EASTMONEY_SIDEBAR_START_Y_RATIO = 0.082
EASTMONEY_SIDEBAR_ITEM_HEIGHT_RATIO = 0.036

# 这些目标优先走快捷键（比侧栏坐标点击更稳）
SHORTCUT_FIRST_TARGETS: frozenset[str] = frozenset(
    {"自选股", "上证指数", "深证成指", "行情"}
)

EASTMONEY_WINDOW_RE = r".*(东方财富|财富终端|经典版).*"

APP_WINDOW_PATTERNS: dict[str, str] = {
    "eastmoney": EASTMONEY_WINDOW_RE,
    "ths": r".*(同花顺|Hexin|hexin).*",
    "wind": r".*(Wind|万得).*",
    "tdx": r".*(通达信|TdxW|tdxw).*",
    "choice": r".*Choice.*",
    "dzh": r".*(大智慧|dzh).*",
}

LOGIN_BUTTONS = {
    "sms": "ButtonLogonSMS",
    "password": "ButtonLogonNormal",
    "qrcode": "ButtonLogonQRCode",
    "guest": "ButtonLogonGuest",
}


@dataclass
class AutomationResult:
    success: bool
    message: str
    steps: list[str] = field(default_factory=list)
    awaiting_user: bool = False


def extract_navigation_target(text: str) -> str | None:
    normalized = re.sub(r"\s+", "", text)
    for target, aliases in NAVIGATION_TARGETS.items():
        for alias in aliases:
            alias_norm = re.sub(r"\s+", "", alias)
            patterns = (
                rf"(?:切换到|切到|打开|进入|查看|看|跳转(?:到)?).*{re.escape(alias_norm)}",
                rf"{re.escape(alias_norm)}(?:一栏|页面|界面|板块)",
                rf"然后.*{re.escape(alias_norm)}",
            )
            for pattern in patterns:
                if re.search(pattern, normalized, flags=re.IGNORECASE):
                    return target
    return None


def _require_pywinauto():
    try:
        from pywinauto import Application, findwindows
        from pywinauto.keyboard import send_keys

        return Application, findwindows, send_keys
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("缺少 pywinauto，请先安装：pip install pywinauto") from exc


def _force_hwnd_foreground(hwnd: int) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        user32 = ctypes.windll.user32
        SW_RESTORE = 9
        ASFW_ANY = -1
        VK_MENU = 0x12
        KEYEVENTF_KEYUP = 0x0002

        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        user32.AllowSetForegroundWindow(ASFW_ANY)
        user32.keybd_event(VK_MENU, 0, 0, 0)
        user32.SetForegroundWindow(hwnd)
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        user32.BringWindowToTop(hwnd)
    except Exception:
        pass


def _focus_window(window) -> bool:
    try:
        if hasattr(window, "is_minimized") and window.is_minimized():
            window.restore()
        elif hasattr(window, "was_maximized"):
            try:
                if window.get_show_state() == 2:  # SW_SHOWMINIMIZED
                    window.restore()
            except Exception:
                pass
        _force_hwnd_foreground(int(window.handle))
        window.set_focus()
        return True
    except Exception:
        return False


def _wait_for_app_window(title_re: str, timeout: float = 20.0):
    Application, findwindows, _send_keys = _require_pywinauto()
    deadline = time.time() + timeout
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            handles = findwindows.find_windows(title_re=title_re)
            for handle in reversed(handles):
                app = Application(backend="uia").connect(handle=handle)
                window = app.window(handle=handle)
                if window.exists(timeout=0.5):
                    return app, window
        except Exception as exc:
            last_error = exc
        time.sleep(0.6)

    if last_error:
        raise TimeoutError(f"等待应用窗口超时：{last_error}")
    raise TimeoutError("等待应用窗口超时")


def bring_app_window_to_front(app_id: str, timeout: float = 15.0) -> tuple[bool, str]:
    if sys.platform != "win32":
        return False, "当前系统暂不支持窗口置顶。"

    title_re = APP_WINDOW_PATTERNS.get(app_id)
    if not title_re:
        return False, "未配置该应用的窗口匹配规则。"

    try:
        _app, window = _wait_for_app_window(title_re, timeout=timeout)
        if _focus_window(window):
            return True, "已将应用窗口置于最前。"
        return False, "已找到应用窗口，但置顶失败。"
    except Exception as exc:
        return False, f"未能将应用窗口置顶：{exc}"


def _wait_for_eastmoney_window(timeout: float = 30.0):
    return _wait_for_app_window(EASTMONEY_WINDOW_RE, timeout=timeout)


def _click_if_exists(window, title: str, control_type: str = "Button", timeout: float = 1.5) -> bool:
    try:
        button = window.child_window(title=title, control_type=control_type)
        if button.exists(timeout=timeout):
            button.click_input()
            return True
    except Exception:
        return False
    return False


def _login_dialog_visible(window) -> bool:
    for button_id in LOGIN_BUTTONS.values():
        try:
            if window.child_window(title=button_id, control_type="Button").exists(timeout=0.4):
                return True
        except Exception:
            continue
    return False


def _assist_eastmoney_login(
    window,
    phone: str | None,
    login_method: str,
    copy_phone,
) -> tuple[list[str], bool]:
    _, _, send_keys = _require_pywinauto()
    steps: list[str] = []

    if not _login_dialog_visible(window):
        steps.append("未检测到登录弹窗，可能已保持登录状态。")
        return steps, False

    method = login_method if login_method in LOGIN_BUTTONS else "sms"
    if method == "unknown":
        method = "sms" if phone else "guest"

    if method == "guest":
        if _click_if_exists(window, LOGIN_BUTTONS["guest"]):
            steps.append("已尝试游客浏览进入软件。")
            time.sleep(2.5)
            return steps, False
        steps.append("检测到登录弹窗，但未提供手机号，无法自动完成账号登录。")
        return steps, True

    if not phone:
        steps.append("检测到登录弹窗，请先在指令中提供手机号，或手动完成登录。")
        return steps, True

    if not _click_if_exists(window, LOGIN_BUTTONS.get(method, LOGIN_BUTTONS["sms"])):
        steps.append("未能切换到短信登录页，请手动选择登录方式。")
        return steps, True

    steps.append("已切换到短信验证码登录。")
    time.sleep(0.8)
    window.set_focus()

    clipboard_ok = copy_phone(phone)
    if clipboard_ok:
        send_keys("^a", pause=0.05)
        send_keys("^v", pause=0.1)
        steps.append("已尝试将手机号粘贴到登录框。")
    else:
        send_keys("^a", pause=0.05)
        send_keys(phone, with_spaces=True, pause=0.03)
        steps.append("已尝试将手机号输入到登录框。")

    steps.append("请在软件中点击「获取验证码」，并在手机收到短信后手动输入验证码。")
    return steps, True


def _sidebar_item_index(item: str) -> int | None:
    if item in EASTMONEY_SIDEBAR_MENU:
        return EASTMONEY_SIDEBAR_MENU.index(item)
    aliases = {
        "全景": "全景",
        "自选股": "自选",
        "自选": "自选",
        "沪深京": "沪深京",
    }
    mapped = aliases.get(item)
    if mapped and mapped in EASTMONEY_SIDEBAR_MENU:
        return EASTMONEY_SIDEBAR_MENU.index(mapped)
    return None


def _sidebar_click_point(window, item: str) -> tuple[int, int] | None:
    index = _sidebar_item_index(item)
    if index is None:
        return None
    rect = window.rectangle()
    width = max(rect.width(), 1)
    height = max(rect.height(), 1)
    x = rect.left + int(width * EASTMONEY_SIDEBAR_X_RATIO)
    y = rect.top + int(
        height
        * (
            EASTMONEY_SIDEBAR_START_Y_RATIO
            + index * EASTMONEY_SIDEBAR_ITEM_HEIGHT_RATIO
            + EASTMONEY_SIDEBAR_ITEM_HEIGHT_RATIO / 2
        )
    )
    return x, y


def _click_sidebar_item(window, item: str) -> bool:
    point = _sidebar_click_point(window, item)
    if not point:
        return False
    try:
        window.set_focus()
        time.sleep(0.2)
        window.click_input(coords=point)
        time.sleep(0.8)
        return True
    except Exception:
        return False


def _find_and_click_text(window, text: str) -> bool:
    try:
        for control_type in ("Text", "Button", "TabItem", "ListItem", "MenuItem"):
            try:
                target = window.child_window(title=text, control_type=control_type)
                if target.exists(timeout=0.5):
                    target.click_input()
                    time.sleep(0.8)
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def _send_shortcut(window, target: str, shortcut: str) -> list[str]:
    _, _, send_keys = _require_pywinauto()
    window.set_focus()
    time.sleep(0.35)
    send_keys(shortcut, pause=0.1)
    time.sleep(0.6)
    key = shortcut.strip("{}")
    if target == "自选股":
        return [f"已发送快捷键 {key}，切换到自选股页面。"]
    if target in {"上证指数", "深证成指"}:
        return [f"已发送快捷键 {key}，进入{target}分时图。"]
    return [f"已发送快捷键 {key}，切换到「{target}」。"]


def _navigate_eastmoney(window, target: str) -> list[str]:
    shortcut = NAVIGATION_SHORTCUTS.get(target)
    if shortcut and target in SHORTCUT_FIRST_TARGETS:
        return _send_shortcut(window, target, shortcut)

    if target == "大盘":
        if _find_and_click_text(window, "大盘"):
            return ["已点击左侧导航栏「大盘」，切换到指数列表页面。"]
        if _click_sidebar_item(window, "大盘"):
            return ["已点击左侧导航栏「大盘」，切换到指数列表页面（沪深重要指数）。"]
        return ["未能定位「大盘」导航入口，请手动点击左侧「大盘」。"]

    if _sidebar_item_index(target) is not None:
        label = "自选" if target == "自选股" else target
        if _find_and_click_text(window, label) or _click_sidebar_item(window, label):
            return [f"已点击左侧导航「{label}」。"]
        if shortcut:
            return _send_shortcut(window, target, shortcut)
        return [f"未能定位「{label}」导航入口，请手动切换。"]

    if not shortcut:
        return [f"暂不支持自动切换到「{target}」。"]

    return _send_shortcut(window, target, shortcut)


def run_eastmoney_automation(
    *,
    phone: str | None = None,
    login_method: str = "unknown",
    navigate_to: str | None = None,
    wants_login: bool = False,
    copy_phone,
    window_timeout: float = 30.0,
) -> AutomationResult:
    if sys.platform != "win32":
        return AutomationResult(
            success=False,
            message="当前系统暂不支持桌面 UI 自动化。",
            steps=[],
        )

    steps: list[str] = []
    awaiting_user = False

    try:
        _app, window = _wait_for_eastmoney_window(timeout=window_timeout)
        steps.append("已连接到东方财富窗口。")
        if _focus_window(window):
            steps.append("已将东方财富窗口置于浏览器上方。")

        if wants_login or phone or _login_dialog_visible(window):
            login_steps, awaiting_user = _assist_eastmoney_login(
                window,
                phone=phone,
                login_method=login_method,
                copy_phone=copy_phone,
            )
            steps.extend(login_steps)

        if navigate_to:
            if awaiting_user and _login_dialog_visible(window):
                fallback = (
                    "点击左侧「大盘」"
                    if navigate_to == "大盘"
                    else NAVIGATION_SHORTCUTS.get(navigate_to, "").strip("{}")
                    or "对应快捷键"
                )
                steps.append(
                    f"登录尚未完成，暂未自动切换到「{navigate_to}」。"
                    f"完成验证码后，请手动{fallback}进入该页面。"
                )
            else:
                if awaiting_user:
                    time.sleep(1.5)
                steps.extend(_navigate_eastmoney(window, navigate_to))

        message = "\n".join(steps) if steps else "自动化步骤已执行。"
        return AutomationResult(
            success=True,
            message=message,
            steps=steps,
            awaiting_user=awaiting_user,
        )
    except Exception as exc:
        return AutomationResult(
            success=False,
            message=f"桌面自动化失败：{exc}",
            steps=steps,
            awaiting_user=awaiting_user,
        )
