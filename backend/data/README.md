# 研究资料库 `corpus.json`

侧边栏 **「同步资料库」** 会读取本文件，经 Embedding 后写入 Supabase 表 `financial_documents`。

## 单条文档格式

```json
{
  "content": "公司/宏观文字摘要，建议 200～800 字",
  "metadata": {
    "ticker": "AAPL",
    "sector": "Technology",
    "source": "10-K FY2025",
    "type": "earnings",
    "fiscal_year": 2025,
    "is_latest": true
  }
}
```

| 字段 | 说明 |
|------|------|
| `content` | 必填，检索与 RAG 的正文 |
| `metadata.ticker` | 股票代码或 `MACRO` |
| `metadata.source` | 来源（财报、电话会、FOMC 等） |
| `metadata.type` | `earnings` / `macro` / `research` 等 |
| `metadata.is_latest` | 可选，标记该标的当前最新披露 |

## 扩展资料

1. 在 `documents` 数组中追加对象并保存。
2. 在前端再次点击「同步资料库」（默认 `replace: true` 会先清空向量表再写入）。

## 相关代码

- 加载：`backend/corpus.py` → `get_library_documents()`
- 同步 API：`POST /api/ingest`（`use_library: true`, `replace: true`）
- 状态：`GET /api/corpus/status`
