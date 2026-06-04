# Finsight Dashboard

**金融文档 RAG 研究智能体** —— Next.js 14 终端风格中文界面、FastAPI 后端、LlamaIndex RAG、DeepSeek 大模型与 Supabase pgvector 向量检索。

![Stack](https://img.shields.io/badge/Next.js-14-black) ![FastAPI](https://img.shields.io/badge/FastAPI-Python-green) ![LlamaIndex](https://img.shields.io/badge/RAG-LlamaIndex-blue) ![Supabase](https://img.shields.io/badge/Vector-pgvector-3ecf8e)

## 演示视频

<video width="100%" controls playsinline src="https://github.com/FrontEnd-Liang/Finsight-dashboard/raw/main/assets/demo.mp4">
  您的浏览器不支持内嵌播放，请
  <a href="./assets/demo.mp4">下载演示视频</a>
  或在仓库中打开 <code>assets/demo.mp4</code>。
</video>

> 本地克隆后可直接打开 [`assets/demo.mp4`](./assets/demo.mp4)。GitHub 网页若无法内嵌播放，请使用上方 raw 链接或下载文件观看。

## 核心能力

| 能力 | 说明 |
|------|------|
| **RAG 问答** | 基于 Supabase pgvector 检索财报/宏观资料，流式生成研究结论 |
| **思考过程** | 分步状态 + 逐行流式展示检索策略、命中文档摘录与分析规划，再输出正文 |
| **引用溯源** | 回答底部标注 ticker、来源文档、相似度分数 |
| **资料库管理** | 从 `corpus.json` 同步至向量索引，支持清空后全量重导 |
| **智能推荐问** | 根据资料库覆盖标的生成快捷提问（会话级缓存，可手动刷新） |
| **交互增强** | 流式输出、停止生成、多会话、回答点赞/点踩 |
| **负反馈闭环** | 点踩写入 Supabase，定时脚本用独立模型修订 `corpus.json` 并可选重导向量库 |
| **空检索兜底** | 无匹配上下文时，直连 LLM 给出中文说明（含日期、拒答预测类问题） |

> **说明：** 回答基于已入库的研究资料库，不含实时行情推送；引用中会标明财报/公告所属期间。

## 架构概览

```mermaid
flowchart TB
  subgraph Frontend["Next.js 终端 UI"]
    Chat[对话 / 思考过程 / 反馈]
    Side[资料库 / 会话]
    Input[推荐问题 / 停止生成]
  end

  subgraph API["FastAPI"]
    ChatAPI["/api/chat SSE"]
    Ingest["/api/ingest"]
    Suggest["/api/suggestions"]
    Status["/api/corpus/status"]
  end

  subgraph Agent["FinancialResearchAgent"]
    Retrieve[向量检索]
    Think[检索摘要]
    Answer[流式合成]
    Fallback[空响应兜底 LLM]
  end

  Chat --> ChatAPI
  Side --> Ingest
  Side --> Status
  Input --> Suggest
  ChatAPI --> Agent
  Retrieve --> VS[(Supabase pgvector)]
  Answer --> LLM[DeepSeek API]
  Fallback --> LLM
  Retrieve --> Embed[Embedding API]
```

## 项目结构

```
├── assets/
│   └── demo.mp4              # 产品演示录屏
├── app/                      # Next.js App Router 主页面
├── components/
│   ├── chat/                 # ChatInput、ChatMessage、Markdown
│   └── layout/               # Sidebar（资料库 / 会话）
├── lib/
│   ├── api.ts                # SSE、资料库、推荐问题 API 客户端
│   └── sessions.ts           # 会话与消息 localStorage
├── backend/
│   ├── agent.py              # RAG Agent、思考流、兜底逻辑
│   ├── corpus.py             # 资料库 JSON 加载与校验
│   ├── data/
│   │   ├── corpus.json       # 机构研究资料清单（可编辑）
│   │   └── README.md         # 资料格式说明
│   ├── config.py
│   ├── database.py           # Supabase + pgvector RPC
│   ├── embeddings.py
│   ├── llm.py                # DeepSeek OpenAI 兼容封装
│   ├── main.py               # FastAPI 路由
│   ├── requirements.txt
│   └── supabase_schema.sql
├── package.json
└── README.md
```

## 前端界面

| 区域 | 说明 |
|------|------|
| **侧边栏** | 新建研究、同步资料库（含结果提示）、会话历史、资料库状态（条数 / 标的 / 披露截至日） |
| **主面板** | 分析师提问 + Finsight 智能体回复；思考时自动展开「思考过程」并显示当前步骤 |
| **回答区** | Markdown 渲染、引用来源（含摘录与元数据）、重新生成 / 复制 / 朗读、点赞/点踩 |
| **输入区** | 推荐快捷问题、刷新按钮、流式发送 / **停止生成** |
| **状态栏** | 就绪 / 思考中 / 生成回答 / 同步资料库 等 |

## 环境要求

- Node.js 18+
- Python 3.10+
- [Supabase](https://supabase.com) 项目（需 SQL 访问权限）
- [DeepSeek](https://platform.deepseek.com) API Key
- OpenAI 兼容 **Embedding** 服务（见 `.env` 配置，可与 DeepSeek 分离）

## 快速开始

### 1. 数据库初始化

在 Supabase SQL Editor 中执行：

```
backend/supabase_schema.sql
```

将启用 `pgvector`、创建 `financial_documents` 表及 `match_financial_documents` RPC。

再执行反馈表（点踩记录）：

```
backend/supabase_feedback.sql
```

### 2. 后端

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# 编辑 .env 填入密钥
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3. 前端

```powershell
cd ..
npm install
copy .env.local.example .env.local
npm run dev
```

浏览器访问 [http://localhost:3000](http://localhost:3000)。

### 环境变量

**`backend/.env`**

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `DEEPSEEK_BASE_URL` | 默认 `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 如 `deepseek-chat`、`deepseek-v4-pro` |
| `DEEPSEEK_CONTEXT_WINDOW` | 上下文窗口（可选） |
| `CHAT_MAX_TOKENS` | 单次回答 token 上限（默认 2048） |
| `RAG_TOP_K` | 检索条数（默认 5） |
| `SUPABASE_URL` | Supabase 项目 URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Service Role Key（**仅服务端**） |
| `EMBEDDING_API_KEY` | Embedding 服务 Key |
| `EMBEDDING_BASE_URL` | OpenAI 兼容 Embedding 基址 |
| `EMBEDDING_MODEL` | 如 `BAAI/bge-m3` |
| `EMBEDDING_DIMENSIONS` | 须与 `supabase_schema.sql` 中 vector 维度一致（默认 1024） |
| `REFINEMENT_API_KEY` | 资料库修订模型 Key（默认可同 `EMBEDDING_API_KEY`） |
| `REFINEMENT_BASE_URL` | 须为 SiliconFlow 等，**不可**用 DeepSeek |
| `REFINEMENT_MODEL` | 如 `Qwen/Qwen2.5-72B-Instruct` |
| `CORS_ORIGINS` | `http://localhost:3000` |

**`.env.local`（前端）**

| 变量 | 说明 |
|------|------|
| `NEXT_PUBLIC_API_URL` | 默认 `http://localhost:8000` |

> **Embedding 说明：** 对话走 DeepSeek；向量嵌入使用独立 OpenAI 兼容端点（如 SiliconFlow）。若维度与库表不一致，需同步修改 SQL 与 `EMBEDDING_DIMENSIONS`。

## 研究资料库

资料清单位于 [`backend/data/corpus.json`](backend/data/corpus.json)，当前覆盖：

`AAPL` · `MSFT` · `NVDA` · `GOOGL` · `AMZN` · `TSLA` · `JPM` · `MACRO`（FOMC）

扩展格式见 [`backend/data/README.md`](backend/data/README.md)。

## 使用流程

1. 启动后端 `uvicorn` 与前端 `npm run dev`。
2. 侧边栏点击 **「同步资料库」**，确认底部状态为「已索引 N 条」且与清单条数一致。
3. 点击推荐问题或输入研究问题，例如：*「对比 AAPL 与 MSFT 营收增速及利润率，并以 Markdown 表格输出。」*
4. 观察 **思考过程** → **正文流式输出** → **引用来源**。

### 示例问题

- 对比 AAPL 与 MSFT 营收增速及利润率
- 汇总 NVDA 数据中心业务前景（基于公告/财报）
- 最新 FOMC 对 2026 年下半年利率路径释放何种信号？
- 生成超大盘科技 KPI 对比 Markdown 表格

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/api/chat` | SSE 流式对话（`query`, `session_id`） |
| `POST` | `/api/suggestions` | 推荐提问（`recent_queries`, `count`） |
| `GET` | `/api/corpus/status` | 向量库条数、资料清单元信息 |
| `POST` | `/api/ingest` | 导入文档（`use_library`, `replace`, 或 `documents`） |
| `POST` | `/api/feedback` | 提交点赞/点踩（点踩进入修订队列） |
| `DELETE` | `/api/feedback/{session_id}/{message_id}` | 取消反馈记录 |
| `POST` | `/api/reset` | 清除指定会话的服务端对话记忆 |

### `POST /api/ingest` 示例

```json
{
  "use_library": true,
  "replace": true
}
```

响应示例：

```json
{
  "ingested_nodes": 12,
  "stored_count": 12,
  "status": "success",
  "replaced": true
}
```

### SSE 事件格式

```text
data: {"type": "thinking_step", "label": "检索资料库（向量相似度）…"}
data: {"type": "thinking", "content": "## 问题理解\n"}
data: {"type": "token", "content": "部分正文"}
data: {"type": "done", "sources": [{"ticker": "AAPL", "source": "10-K FY2025", "score": 0.82, "excerpt": "..."}]}
data: {"type": "error", "message": "..."}
```

| `type` | 含义 |
|--------|------|
| `thinking_step` | 思考阶段状态文案（如理解问题、检索、逐条核对） |
| `thinking` | 思考过程 Markdown 增量（按行推送） |
| `token` | 正式回答正文增量 |
| `done` | 流结束，附带完整 `sources`（含摘录、披露元数据） |
| `error` | 错误信息 |

## 常见问题

### 回答显示 `Empty Response`

多因 **无可用检索上下文** 时框架返回占位符。当前版本已放宽检索并增加兜底 LLM；前端会过滤 `Empty Response` 字面量。

若仍出现：请 **新建研究会话**、确认已同步资料库，并避免在 `uvicorn --reload` 保存文件的瞬间提问。

### 指数/股价预测类问题

资料库 **不含实时行情**，智能体会说明无法负责任预测，并给出应关注的宏观/市场变量框架。

### 引用期间与「今天」不一致

RAG 只返回已入库披露片段；回答中会标注 FY/季度。若需更新，请编辑 `corpus.json` 后重新 **同步资料库**。

### 推荐问题每次发消息都刷新

已改为 **按会话 + 资料版本缓存**；仅在进入页面、切换会话、同步资料库或点击刷新按钮时重新请求。

## 点踩反馈与资料库自动修订

1. 用户对回答点踩 → `POST /api/feedback` 写入 `message_feedback`（status=`pending`）。
2. 定时任务运行修订脚本（使用 **REFINEMENT_*** 模型，与对话用 DeepSeek 分离）：

```powershell
cd backend
.\venv\Scripts\activate
python scripts/process_feedback.py --limit 10 --reingest
```

Windows 计划任务可执行 `backend/scripts/run_feedback_job.ps1`（建议每 6–12 小时）。

| 参数 | 说明 |
|------|------|
| `--dry-run` | 只调用修订模型，不写 `corpus.json` |
| `--reingest` | 补丁成功后自动同步向量库 |
| `--limit N` | 单次最多处理 N 条点踩 |

修订前会自动备份至 `backend/data/backups/`。处理完成后请在终端 **同步资料库** 或依赖 `--reingest`。

## 生产部署注意事项

- 切勿将 `SUPABASE_SERVICE_ROLE_KEY` 暴露到浏览器。
- 为 `financial_documents` 配置 RLS（若 Supabase 对客户端开放）。
- 生产建议使用 `gunicorn` + `uvicorn` workers，置于反向代理之后。
- 设置 `NEXT_PUBLIC_API_URL` 为线上 API 地址。
