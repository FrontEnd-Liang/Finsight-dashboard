# 演示语料库 `demo_corpus.json`

侧边栏 **「加载演示语料库」** 会读取本文件，经 Embedding 后写入 Supabase 表 `financial_documents`。

## 单条文档格式

```json
{
  "content": "公司/宏观文字摘要，建议 200～800 字",
  "metadata": {
    "ticker": "AAPL",
    "sector": "Technology",
    "source": "10-K FY2024",
    "type": "earnings",
    "fiscal_year": 2024
  }
}
```

| 字段 | 说明 |
|------|------|
| `content` | 必填，检索与 RAG 的正文 |
| `metadata.ticker` | 股票代码或 `MACRO` |
| `metadata.source` | 来源（财报、电话会、FOMC 等） |
| `metadata.type` | `earnings` / `macro` 等 |

## 扩展语料

1. 在 `documents` 数组中追加对象并保存。
2. 重启无需；在前端再次点击「加载演示语料库」（默认 `replace: true` 会先清空向量表再写入）。

## 相关代码

- 加载：`backend/corpus.py` → `get_demo_documents()`
- 注入 API：`POST /api/ingest`（`use_demo: true`, `replace: true`）
- 状态：`GET /api/corpus/status`
