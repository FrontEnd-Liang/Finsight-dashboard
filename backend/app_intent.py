"""Parse compound desktop-app commands (launch + optional login assist)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app_automation import extract_navigation_target
from app_launcher import FINANCIAL_APPS, _normalize

LAUNCH_VERBS = ("打开", "启动", "运行", "开启", "launch", "open", "start")
LOGIN_VERBS = ("登录", "登陆", "登入", "signin", "sign in", "login")
GENERIC_ALIASES = ("金融软件", "炒股软件", "交易软件", "行情软件")

LoginMethod = Literal["sms", "password", "unknown"]


@dataclass(frozen=True)
class AppCommandIntent:
    matched: bool
    launch: bool = False
    login: bool = False
    app_target: str | None = None
    phone: str | None = None
    login_method: LoginMethod = "unknown"
    navigate_to: str | None = None
    raw_query: str = ""


PHONE_PATTERNS = (
    re.compile(r"(?:手机号|手机号码|电话|账号|帐户|账户)\s*(?:为|是|:|：)?\s*(1[3-9]\d{9})"),
    re.compile(r"(1[3-9]\d{9})\s*(?:的手机号|手机号|账号|帐户|账户)"),
    re.compile(r"(?:使用|用)\s*(1[3-9]\d{9})"),
    re.compile(r"(1[3-9]\d{9})"),
)


def _extract_phone(text: str) -> str | None:
    for pattern in PHONE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def _extract_login_method(text: str) -> LoginMethod:
    normalized = _normalize(text)
    if any(key in normalized for key in ("验证码", "短信", "sms", "动态码")):
        return "sms"
    if any(key in normalized for key in ("密码", "password", "口令")):
        return "password"
    return "unknown"


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    normalized = _normalize(text)
    return any(_normalize(keyword) in normalized for keyword in keywords)


def _extract_app_target(text: str) -> str | None:
    normalized = _normalize(text)

    for alias in GENERIC_ALIASES:
        if _normalize(alias) in normalized:
            return alias

    best: tuple[int, str] | None = None
    for app in FINANCIAL_APPS:
        for alias in app.aliases:
            alias_norm = _normalize(alias)
            if alias_norm and alias_norm in normalized:
                score = len(alias_norm)
                if best is None or score > best[0]:
                    best = (score, alias)
    return best[1] if best else None


def _has_launch_intent(text: str) -> bool:
    if _contains_any(text, LAUNCH_VERBS):
        return True
    return bool(re.search(r"^(打开|启动|运行|开启)\b", text.strip(), flags=re.IGNORECASE))


def _has_login_intent(text: str) -> bool:
    return _contains_any(text, LOGIN_VERBS)


def _has_navigation_intent(text: str) -> bool:
    return extract_navigation_target(text) is not None


def _build_intent(
    *,
    query: str,
    launch: bool,
    login: bool,
    app_target: str | None,
    phone: str | None,
    login_method: LoginMethod,
) -> AppCommandIntent:
    return AppCommandIntent(
        matched=True,
        launch=launch,
        login=login,
        app_target=app_target,
        phone=phone,
        login_method=login_method,
        navigate_to=extract_navigation_target(query),
        raw_query=query,
    )


def parse_app_command(query: str) -> AppCommandIntent:
    text = query.strip()
    if not text:
        return AppCommandIntent(matched=False, raw_query=query)

    launch = _has_launch_intent(text)
    login = _has_login_intent(text)
    phone = _extract_phone(text)
    login_method = _extract_login_method(text) if login else "unknown"
    app_target = _extract_app_target(text)

    navigate_to = extract_navigation_target(text)
    if launch or login or app_target or navigate_to:
        if login and phone:
            return _build_intent(
                query=query,
                launch=launch or bool(app_target),
                login=True,
                app_target=app_target,
                phone=phone,
                login_method=login_method,
            )
        if launch and app_target:
            return _build_intent(
                query=query,
                launch=True,
                login=login,
                app_target=app_target,
                phone=phone,
                login_method=login_method,
            )
        if launch:
            return _build_intent(
                query=query,
                launch=True,
                login=login,
                app_target=app_target or "金融软件",
                phone=phone,
                login_method=login_method,
            )
        if navigate_to:
            return _build_intent(
                query=query,
                launch=launch or bool(app_target),
                login=login,
                app_target=app_target,
                phone=phone,
                login_method=login_method,
            )

    return AppCommandIntent(matched=False, raw_query=query)
