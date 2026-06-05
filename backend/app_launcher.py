"""Detect and launch common financial desktop apps on Windows."""

from __future__ import annotations

import glob
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

LAUNCH_VERBS = ("打开", "启动", "运行", "开启", "launch", "open", "start")
GENERIC_ALIASES = ("金融软件", "炒股软件", "交易软件", "行情软件")


@dataclass(frozen=True)
class FinancialApp:
    id: str
    name: str
    aliases: tuple[str, ...]
    exe_names: tuple[str, ...]
    common_paths: tuple[str, ...]


FINANCIAL_APPS: tuple[FinancialApp, ...] = (
    FinancialApp(
        id="ths",
        name="同花顺",
        aliases=("同花顺", "同花顺软件", "hexin"),
        exe_names=("hexin.exe", "xiadan.exe"),
        common_paths=(
            r"C:\同花顺软件\同花顺\hexin.exe",
            r"C:\同花顺软件\同花顺\xiadan.exe",
            r"C:\Program Files\同花顺\hexin.exe",
            r"C:\Program Files (x86)\同花顺\hexin.exe",
            r"C:\hexin\hexin.exe",
        ),
    ),
    FinancialApp(
        id="eastmoney",
        name="东方财富",
        aliases=("东方财富", "东财", "eastmoney", "东方财富证券"),
        exe_names=(
            "mainfree.exe",
            "maintrade.exe",
            "main.exe",
            "stockway.exe",
            "emswc.exe",
        ),
        common_paths=(
            r"H:\dfcf\mainfree.exe",
            r"H:\dfcf\maintrade.exe",
            r"C:\eastmoney\swc8\main.exe",
            r"C:\eastmoney\eastmoney\main.exe",
            r"D:\eastmoney\swc8\main.exe",
            r"D:\dfcf\mainfree.exe",
            r"E:\dfcf\mainfree.exe",
            r"F:\dfcf\mainfree.exe",
            r"G:\dfcf\mainfree.exe",
            r"C:\Program Files\eastmoney\swc8\main.exe",
            r"C:\Program Files (x86)\eastmoney\swc8\main.exe",
            r"*\dfcf\mainfree.exe",
            r"*\dfcf\maintrade.exe",
            r"*\eastmoney\swc8\main.exe",
        ),
    ),
    FinancialApp(
        id="wind",
        name="Wind金融终端",
        aliases=("wind", "万得", "wind终端", "wind金融终端"),
        exe_names=("WFT.exe", "WindNET.exe", "Wind.exe"),
        common_paths=(
            r"C:\Wind\Wind.NET.Client\WFT\WFT.exe",
            r"C:\Wind\Wind.NET.Client\WindNET.exe",
            r"C:\Program Files\Wind\Wind.NET.Client\WFT\WFT.exe",
        ),
    ),
    FinancialApp(
        id="tdx",
        name="通达信",
        aliases=("通达信", "tdx"),
        exe_names=("TdxW.exe", "tdxw.exe"),
        common_paths=(
            r"C:\new_tdx\TdxW.exe",
            r"C:\tdx\TdxW.exe",
            r"C:\Program Files\new_tdx\TdxW.exe",
            r"C:\Program Files (x86)\new_tdx\TdxW.exe",
        ),
    ),
    FinancialApp(
        id="choice",
        name="Choice金融终端",
        aliases=("choice", "choice终端", "choice金融终端"),
        exe_names=("Choice.exe", "EmChoice.exe"),
        common_paths=(
            r"C:\Choice\Choice.exe",
            r"C:\Program Files\Choice\Choice.exe",
            r"C:\eastmoney\Choice\Choice.exe",
        ),
    ),
    FinancialApp(
        id="dzh",
        name="大智慧",
        aliases=("大智慧", "dzh"),
        exe_names=("dzh2.exe", "dzh.exe"),
        common_paths=(
            r"C:\dzh2\dzh2.exe",
            r"C:\Program Files\dzh2\dzh2.exe",
            r"C:\Program Files (x86)\dzh2\dzh2.exe",
        ),
    ),
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text.strip().lower())


def parse_launch_intent(query: str) -> tuple[str | None, str | None]:
    """Return (verb_matched_target, raw_target) or (None, None) if not a launch command."""
    text = query.strip()
    if not text:
        return None, None

    verb_pattern = "|".join(re.escape(v) for v in LAUNCH_VERBS)
    match = re.match(rf"^({verb_pattern})\s*(.+)$", text, flags=re.IGNORECASE)
    if not match:
        return None, None

    target = match.group(2).strip().rstrip("。！!？?")
    if not target:
        return None, None
    return match.group(1), target


def _resolve_app(target: str) -> FinancialApp | None:
    normalized = _normalize(target)
    if normalized in {_normalize(a) for a in GENERIC_ALIASES}:
        return None

    for app in FINANCIAL_APPS:
        for alias in app.aliases:
            alias_norm = _normalize(alias)
            if alias_norm == normalized or alias_norm in normalized or normalized in alias_norm:
                return app
    return None


def _is_generic_target(target: str) -> bool:
    normalized = _normalize(target)
    return normalized in {_normalize(a) for a in GENERIC_ALIASES}


def _search_roots() -> list[str]:
    roots: list[str] = []
    for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA", "APPDATA"):
        value = os.environ.get(key)
        if value and value not in roots:
            roots.append(value)
    return roots


def _path_exists(path: str) -> bool:
    try:
        return os.path.isfile(path)
    except OSError:
        return False


def _shortcut_dirs() -> list[Path]:
    dirs: list[Path] = []
    candidates = [
        Path(os.environ.get("USERPROFILE", "")) / "Desktop",
        Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "Desktop",
        Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs",
        Path(os.environ.get("ProgramData", "")) / r"Microsoft\Windows\Start Menu\Programs",
    ]
    for path in candidates:
        if path.exists() and path not in dirs:
            dirs.append(path)
    return dirs


def _read_windows_shortcut(path: Path) -> tuple[str, str] | None:
    if sys.platform != "win32":
        return None
    try:
        from win32com.client import Dispatch  # type: ignore[import-untyped]

        shell = Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(path))
        return str(shortcut.TargetPath), str(shortcut.WorkingDirectory)
    except Exception:
        pass

    try:
        import struct

        with path.open("rb") as handle:
            data = handle.read()
        if len(data) < 0x4C or data[:4] != b"L\x00\x00\x00":
            return None
        flags = struct.unpack("<I", data[0x14:0x18])[0]
        pos = 0x4C
        if flags & 0x1:
            while pos < len(data) - 1 and not (data[pos] == 0 and data[pos + 1] == 0):
                pos += 2
            pos += 2
        if flags & 0x2:
            while pos < len(data) - 1 and not (data[pos] == 0 and data[pos + 1] == 0):
                pos += 2
            pos += 2
        if flags & 0x4:
            while pos < len(data) and data[pos] != 0:
                pos += 1
            pos += 1
        if flags & 0x8:
            while pos < len(data) - 1 and not (data[pos] == 0 and data[pos + 1] == 0):
                pos += 2
            pos += 2
        if pos >= len(data) - 1:
            return None
        end = pos
        while end < len(data) - 1 and not (data[end] == 0 and data[end + 1] == 0):
            end += 2
        target = data[pos:end].decode("utf-16-le", errors="ignore").strip("\x00")
        if target and _path_exists(target):
            return target, ""
    except OSError:
        return None
    return None


def _find_from_shortcuts(app: FinancialApp) -> str | None:
    if sys.platform != "win32":
        return None

    exe_lower = {name.lower() for name in app.exe_names}
    alias_keys = {_normalize(alias) for alias in app.aliases}
    path_keys = {_normalize(app.id), "dfcf", "eastmoney", "emswc", "swc8"}

    matches: list[tuple[int, str]] = []

    for shortcut_dir in _shortcut_dirs():
        try:
            shortcuts = list(shortcut_dir.glob("*.lnk"))
            shortcuts.extend(shortcut_dir.rglob("*.lnk"))
        except OSError:
            continue

        for shortcut_path in shortcuts:
            resolved = _read_windows_shortcut(shortcut_path)
            if not resolved:
                continue
            target, _workdir = resolved
            if not target.lower().endswith(".exe") or not _path_exists(target):
                continue

            shortcut_key = _normalize(shortcut_path.stem)
            target_key = _normalize(target)
            basename = os.path.basename(target).lower()

            name_hit = any(alias in shortcut_key or shortcut_key in alias for alias in alias_keys)
            path_hit = any(key in target_key for key in path_keys)
            exe_hit = basename in exe_lower

            if not (name_hit or (path_hit and exe_hit) or (name_hit and exe_hit)):
                continue

            score = 0
            if name_hit:
                score += 4
            if path_hit:
                score += 2
            if basename in exe_lower:
                score += 3
            if "trade" in basename or "交易" in shortcut_key:
                score -= 1
            matches.append((score, target))

    if not matches:
        return None

    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1]


def _find_in_registry(app: FinancialApp) -> str | None:
    if sys.platform != "win32":
        return None

    try:
        import winreg
    except ImportError:
        return None

    uninstall_roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    exe_lower = {name.lower() for name in app.exe_names}
    name_keys = {_normalize(alias) for alias in app.aliases} | {_normalize(app.name), _normalize(app.id)}

    for hive, subkey in uninstall_roots:
        try:
            with winreg.OpenKey(hive, subkey) as root:
                for i in range(winreg.QueryInfoKey(root)[0]):
                    try:
                        with winreg.OpenKey(root, winreg.EnumKey(root, i)) as app_key:
                            display_name = _read_reg_str(app_key, "DisplayName") or ""
                            display_key = _normalize(display_name)
                            name_match = any(
                                key in display_key or display_key in key for key in name_keys
                            )
                            install_location = _read_reg_str(app_key, "InstallLocation")
                            display_icon = _read_reg_str(app_key, "DisplayIcon")
                            for candidate in (display_icon, install_location):
                                resolved = _resolve_registry_candidate(candidate, exe_lower)
                                if resolved and (name_match or _path_matches_app(resolved, app)):
                                    return resolved
                    except OSError:
                        continue
        except OSError:
            continue
    return None


def _path_matches_app(path: str, app: FinancialApp) -> bool:
    normalized = _normalize(path)
    keys = {_normalize(app.id), "dfcf", "eastmoney", "emswc", "swc8"}
    keys.update(_normalize(alias) for alias in app.aliases)
    return any(key in normalized for key in keys)


def _read_reg_str(key, name: str) -> str | None:
    try:
        import winreg

        value, _ = winreg.QueryValueEx(key, name)
        if isinstance(value, str) and value.strip():
            return value.strip().strip('"')
    except OSError:
        pass
    return None


def _resolve_registry_candidate(candidate: str | None, exe_lower: set[str]) -> str | None:
    if not candidate:
        return None

    path = candidate.split(",")[0].strip().strip('"')
    if path.lower().endswith(".exe") and os.path.basename(path).lower() in exe_lower:
        if _path_exists(path):
            return path

    if _path_exists(path) and not path.lower().endswith(".exe"):
        for name in exe_lower:
            joined = os.path.join(path, name)
            if _path_exists(joined):
                return joined
    return None


def _find_in_named_dirs(app: FinancialApp) -> str | None:
    exe_lower = {name.lower() for name in app.exe_names}
    keywords = {_normalize(alias) for alias in app.aliases} | {_normalize(app.name), _normalize(app.id)}

    for root in _search_roots():
        root_path = Path(root)
        if not root_path.exists():
            continue
        try:
            for child in root_path.iterdir():
                if not child.is_dir():
                    continue
                child_key = _normalize(child.name)
                if not any(key in child_key or child_key in key for key in keywords):
                    continue
                for exe_name in exe_lower:
                    direct = child / exe_name
                    if direct.is_file():
                        return str(direct)
                    for sub in child.iterdir():
                        if not sub.is_dir():
                            continue
                        nested = sub / exe_name
                        if nested.is_file():
                            return str(nested)
        except OSError:
            continue
    return None


def _expand_drive_globs(pattern: str) -> list[str]:
    if not pattern.startswith("*\\"):
        return glob.glob(pattern)
    tail = pattern[2:]
    hits: list[str] = []
    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        drive_pattern = f"{letter}:\\{tail}"
        hits.extend(glob.glob(drive_pattern))
    return hits


def find_app_executable(app: FinancialApp) -> str | None:
    for path in app.common_paths:
        if _path_exists(path):
            return path
        matches = (
            _expand_drive_globs(path) if path.startswith("*\\") else glob.glob(path)
        )
        for match in matches:
            if _path_exists(match):
                return match

    shortcut_hit = _find_from_shortcuts(app)
    if shortcut_hit:
        return shortcut_hit

    registry_hit = _find_in_registry(app)
    if registry_hit:
        return registry_hit

    return _find_in_named_dirs(app)


def list_installed_apps() -> list[tuple[FinancialApp, str]]:
    installed: list[tuple[FinancialApp, str]] = []
    for app in FINANCIAL_APPS:
        exe = find_app_executable(app)
        if exe:
            installed.append((app, exe))
    return installed


def launch_executable(path: str) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
        return
    subprocess.Popen([path], start_new_session=True)


def handle_launch_request(query: str) -> dict:
    verb, target = parse_launch_intent(query)
    if not verb or not target:
        return {"matched": False}

    if _is_generic_target(target):
        installed = list_installed_apps()
        if not installed:
            return {
                "matched": True,
                "launched": False,
                "message": (
                    "未在本机检测到已安装的金融软件。"
                    "支持检测：同花顺、东方财富、Wind、通达信、Choice、大智慧。"
                ),
                "installed_apps": [],
            }

        app, exe = installed[0]
        try:
            launch_executable(exe)
        except OSError as exc:
            return {
                "matched": True,
                "launched": False,
                "app_id": app.id,
                "app_name": app.name,
                "message": f"已找到 {app.name}，但启动失败：{exc}",
                "installed_apps": [item[0].name for item in installed],
            }

        others = [item[0].name for item in installed[1:]]
        extra = f"本机还安装了：{'、'.join(others)}。" if others else ""
        return {
            "matched": True,
            "launched": True,
            "app_id": app.id,
            "app_name": app.name,
            "message": f"已为您启动 {app.name}。{extra}".strip(),
            "installed_apps": [item[0].name for item in installed],
        }

    app = _resolve_app(target)
    if app is None:
        return {
            "matched": True,
            "launched": False,
            "message": (
                f"未识别「{target}」。"
                "可尝试：打开同花顺 / 打开东方财富 / 打开Wind / 打开通达信 / 打开Choice / 打开大智慧，"
                "或输入「打开金融软件」自动启动已安装软件。"
            ),
            "installed_apps": [item[0].name for item in list_installed_apps()],
        }

    exe = find_app_executable(app)
    if not exe:
        return {
            "matched": True,
            "launched": False,
            "app_id": app.id,
            "app_name": app.name,
            "message": f"未在本机检测到 {app.name}，请先安装后再试。",
            "installed_apps": [item[0].name for item in list_installed_apps()],
        }

    try:
        launch_executable(exe)
    except OSError as exc:
        return {
            "matched": True,
            "launched": False,
            "app_id": app.id,
            "app_name": app.name,
            "message": f"已找到 {app.name}，但启动失败：{exc}",
            "installed_apps": [item[0].name for item in list_installed_apps()],
        }

    return {
        "matched": True,
        "launched": True,
        "app_id": app.id,
        "app_name": app.name,
        "message": f"已为您启动 {app.name}。",
        "installed_apps": [item[0].name for item in list_installed_apps()],
    }
