"""Corpus refinement via a non-DeepSeek OpenAI-compatible model (e.g. SiliconFlow Qwen)."""

from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from config import Settings


def _resolve_refinement_credentials(settings: Settings) -> tuple[str, str, str]:
    api_key = settings.refinement_api_key or settings.embedding_api_key
    api_base = settings.refinement_base_url or settings.embedding_base_url
    model = settings.refinement_model
    if not api_key or not api_base:
        raise ValueError(
            "REFINEMENT_API_KEY / REFINEMENT_BASE_URL (or EMBEDDING_* fallbacks) must be set"
        )
    if "deepseek.com" in api_base.lower():
        raise ValueError(
            "Refinement model must not use DeepSeek. Set REFINEMENT_BASE_URL to SiliconFlow or another provider."
        )
    return api_key, api_base, model


def _parse_refinement_json(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def build_refinement_prompt(
    *,
    user_query: str,
    assistant_content: str,
    thinking: str,
    sources: list[dict[str, Any]],
    corpus_excerpt: str,
) -> str:
    sources_block = json.dumps(sources, ensure_ascii=False, indent=2)
    return f"""用户点踩了以下金融研究问答，认为回答无帮助或证据不足。请分析根因，并给出对资料库 corpus.json 的修订建议。

## 用户问题
{user_query.strip()}

## 助手回答（被点踩）
{(assistant_content or '').strip()[:6000]}

## 思考过程摘要
{(thinking or '').strip()[:3000]}

## 引用来源
{sources_block}

## 当前资料库摘录
{corpus_excerpt}

请仅输出 JSON（不要 markdown 说明），格式：
{{
  "analysis": "简要说明点踩原因与改进方向（中文）",
  "updates": [
    {{
      "action": "update",
      "match_ticker": "NVDA",
      "match_source_contains": "Q1 FY2026",
      "content": "修订后的完整英文财报摘要段落（200-800字）",
      "metadata": {{
        "ticker": "NVDA",
        "source": "Earnings Release Q1 FY2026",
        "type": "earnings",
        "fiscal_year": 2026,
        "is_latest": true
      }}
    }}
  ]
}}

规则：
- updates 最多 2 条；优先 update 而非 add
- content 须为英文机构研究摘要风格，含可核对数字
- 不要编造无法从上下文推断的实时股价
- 若无法确定如何改资料库，返回空 updates 数组
"""


def refine_feedback_item(
    settings: Settings,
    *,
    user_query: str,
    assistant_content: str,
    thinking: str,
    sources: list[dict[str, Any]],
    corpus_excerpt: str,
) -> dict[str, Any]:
    api_key, api_base, model = _resolve_refinement_credentials(settings)
    client = OpenAI(api_key=api_key, base_url=api_base)
    prompt = build_refinement_prompt(
        user_query=user_query,
        assistant_content=assistant_content,
        thinking=thinking,
        sources=sources,
        corpus_excerpt=corpus_excerpt,
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是 Finsight 资料库维护工程师。根据用户负反馈修订机构研究资料库，"
                    "只输出合法 JSON。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=4096,
    )
    raw = response.choices[0].message.content or ""
    parsed = _parse_refinement_json(raw)
    if not parsed:
        return {"analysis": "模型返回无法解析，已跳过", "updates": [], "raw": raw[:2000]}
    updates = parsed.get("updates")
    if not isinstance(updates, list):
        updates = []
    return {
        "analysis": str(parsed.get("analysis", "")),
        "updates": updates,
        "raw": raw[:500],
    }
