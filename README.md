# Agentic RAG - 智能工业知识系统

## 项目简介

Agentic RAG 是一个基于 LangChain 和 FastAPI 的智能工业知识系统，专注于 PCB 厂务 / HVAC 领域的知识管理、投标报价复核和技术合规审核。系统采用本地部署架构，确保数据安全可控。

### 核心功能

- **知识问答**：基于 RAG 技术的智能问答系统，支持专业术语理解
- **报价复核**：硬逻辑校验防止 LLM 幻觉，确保报价准确性
- **合规审核**：自动检查投标方案的技术合规性
- **长短期记忆**：支持多轮对话，提供连续上下文理解
- **智能路由**：自动识别用户意图，调用相应工具
- **Human-in-the-Loop**：低置信度时自动触发人工审核

## 技术架构

### 四层架构

```
┌─────────────────────────────────────────────────┐
│ 前端层 (HTML + Tailwind CSS)                   │
├─────────────────────────────────────────────────┤
│ 后端层 (FastAPI)                               │
│ ├── API路由                                    │
│ ├── 业务服务 (rag_service / agent_service)    │
│ └── 记忆管理                                   │
├─────────────────────────────────────────────────┤
│ 核心层 (LangChain + LangGraph + Agent)        │
│ ├── RAG引擎 (AdvancedRAGChain)                │
│ ├── Agent状态机 (AgenticRAGAgent / ReAct)    │
│ └── 工具集                                     │
├─────────────────────────────────────────────────┤
│ 存储层 (Qdrant + 内存会话存储)                │
└─────────────────────────────────────────────────┘
```

### 技术栈

| 类别 | 技术 | 版本 | 用途 |
|------|------|------|------|
| **后端框架** | FastAPI | >=0.104.0 | API 服务 |
| **LLM** | 通义千问 (Qwen) | qwen3.6-plus / qwen-plus | 智能推理 |
| **Embedding** | 通义千问 | text-embedding-v3 / v2 | 文本向量化 |
| **向量库** | Qdrant | >=1.7.0 | 知识存储 |
| **记忆存储** | 内存 | - | 会话管理（Redis 可选） |
| **前端** | HTML + Tailwind CSS | - | 交互界面 |
| **LangChain** | langchain | 1.0.8 | 智能链管理 |
| **LangChain Core** | langchain-core | 1.3.0 | 核心抽象 |
| **LangGraph** | langgraph | 1.0.10 | Agent 状态机 |
| **文档解析** | pypdf / python-docx | - | PDF/DOCX 解析 |

## 快速开始

### 1. 环境要求

- Python 3.8+
- Conda 环境（推荐）：`conda activate agent_rag`
- Qdrant 1.7.0+（本地或 Cloud 版本）
- 通义千问 API Key（DASHSCOPE_API_KEY）

### 2. 安装依赖

```bash
# 1. 克隆项目
cd agent_rag

# 2. 安装全量依赖（推荐）
pip install -r requirements.txt
```

### 3. 配置环境变量

**重点**：配置文件优先使用 `langchain_rag/.env`（而非 `backend/.env`）。

从示例创建配置：
```bash
cp langchain_rag/.env.example langchain_rag/.env
```

编辑 `langchain_rag/.env`，必填项：
```env
# 通义千问 API Key（必须）
DASHSCOPE_API_KEY=sk-...

# Embedding 模型选择
# text-embedding-v3: 1024 维
# text-embedding-v2: 1536 维（与旧集合兼容）
EMBEDDING_MODEL_NAME=text-embedding-v3
EMBEDDING_DIMENSION=1024

# Qdrant 配置（支持 Cloud 完整 URL）
QDRANT_HOST=https://xxx.eu-west-2-0.aws.cloud.qdrant.io
QDRANT_PORT=6334
QDRANT_COLLECTION_NAME=lmf_v1
QDRANT_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 4. 文档灌库

使用配套脚本 `ingest_docs.py` 递归导入 `data/` 目录下的文档（支持子文件夹，文件夹名称自动作为元数据）：

```bash
# Windows
set PYTHONPATH=%CD%;%CD%\langchain_rag
python ingest_docs.py

# Linux/macOS
export PYTHONPATH=$(pwd):$(pwd)/langchain_rag
python ingest_docs.py
```

**功能说明**：
- 自动递归扫描 `data/` 下所有子文件夹
- 文件夹层级自动作为元数据：`category` / `subcategory` / `folder_path`
- 支持格式：PDF / DOCX / TXT / MD / CSV / XLSX / PPTX
- 自动检测 embedding 维度与 Qdrant 集合匹配，不匹配时自动删旧重建

### 5. 启动服务

#### 一键启动（推荐）

```bash
python start.py
```

#### 分别启动

**仅启动后端（开发模式）：**
```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Linux/macOS 启动脚本：**
```bash
# 开发模式（带 reload）
bash start.sh

# 生产模式（gunicorn）
bash start.sh prod
```

**Windows 启动脚本：**
```cmd
start.bat
```

### 6. 访问地址

- **前端界面**: http://localhost:3000
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **Qdrant控制台**: https://cloud.qdrant.io/（如使用 Cloud 版本）

## 项目结构速览

```
agent_rag/
├── langchain_rag/              # 核心 RAG & Agent 库
│   ├── agent/                  # Agent 状态机（LangGraph）
│   │   └── core.py            # AgenticRAGAgent / ReActAgent
│   ├── config/                 # 配置管理
│   │   └── settings.py        # Pydantic v2 配置（统一入口）
│   ├── document/               # 文档加载与处理
│   │   └── processor.py       # 多格式加载 + 中文优化分块
│   ├── examples/               # 使用示例
│   │   └── quickstart.py      # 6 个完整示例
│   ├── llm/                    # LLM 集成
│   │   └── qwen.py            # ChatQwen + Function Calling
│   ├── rag/                    # 检索链
│   │   └── retrieval.py       # AdvancedRAGChain / ConversationalRAGChain
│   ├── tools/                  # Agent 工具集
│   │   └── agent_tools.py     # KnowledgeRetrieval / QuoteValidation / ComplianceCheck
│   ├── vectorstore/            # 向量存储
│   │   └── qdrant.py          # QdrantVectorStore + DashScopeEmbeddings
│   └── tests/                  # 单元测试
│       ├── conftest.py
│       ├── test_qwen.py
│       ├── test_vectorstore.py
│       ├── test_processor.py
│       └── test_agent_tools.py
├── backend/                     # FastAPI 后端
│   ├── api/                     # API 路由
│   ├── services/                # 业务服务（单例模式）
│   │   ├── rag_service.py       # RAG 查询服务
│   │   ├── agent_service.py     # Agent 调用服务
│   │   └── memory_service.py    # 会话记忆服务
│   ├── config/
│   ├── main.py                  # FastAPI 应用入口
│   └── requirements.txt
├── frontend/                    # Web 界面
│   └── index.html
├── data/                        # 文档目录（你要导入的文件放这里）
├── ingest_docs.py               # ✨ 文档灌库脚本（递归 + 文件夹元数据）
├── start.py                     # 一键启动脚本
├── start.sh                     # Linux/macOS 启动
├── start.bat                    # Windows 启动
├── gunicorn_conf.py             # 生产环境 Gunicorn 配置
├── requirements.txt             # 全量依赖
├── langchain_rag/requirements.txt
├── backend/requirements.txt
├── check_config.py              # 配置检查工具
├── CLAUDE.md                    # Claude Code 协作规范
└── README.md                    # 本文档
```

## API 文档

### 核心 API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/rag/query` | POST | RAG 知识查询 |
| `/api/agent/invoke` | POST | Agent 工作流执行 |
| `/api/memory/operation` | POST | 记忆操作（get/clear/save） |
| `/api/memory/sessions` | GET | 列出会话 |
| `/api/agent/tools` | GET | 可用工具列表 |
| `/health` | GET | 健康检查 |

### 示例请求

**RAG 查询：**
```json
POST /api/rag/query
{
  "query": "中央空调系统的 COP 值一般是多少？",
  "session_id": "session_123456"
}
```

**Agent 调用：**
```json
POST /api/agent/invoke
{
  "query": "请帮我复核这份报价",
  "session_id": "session_123456"
}
```

## 知识库管理

### 文档灌库（推荐方式）

使用 `ingest_docs.py`（见前文“快速开始 - 4. 文档灌库”）。

### 手动灌库（高级）

如果你需要更精细的控制，直接使用底层函数：

```python
from langchain_rag.document.processor import load_and_process_documents
from langchain_rag.vectorstore.qdrant import QdrantVectorStore, DashScopeEmbeddings
from langchain_rag.config.settings import config

# 1. 加载并切分文档
docs = load_and_process_documents(
    file_paths=[
        "data/技术规范/中央空调/设计手册.pdf",
        "data/技术规范/冷水机组/选型标准.docx",
    ],
    chunk_size=config.rag.chunk_size,
    chunk_overlap=config.rag.chunk_overlap,
    document_type="技术文档",
)

# 2. 存入 Qdrant
embeddings = DashScopeEmbeddings(
    model_name=config.embedding.model_name,
    api_key=config.embedding.effective_api_key,
)
vectorstore = QdrantVectorStore.from_documents(
    documents=docs,
    embeddings=embeddings,
    host=config.vectorstore.host,
    port=config.vectorstore.port,
    collection_name=config.vectorstore.collection_name,
    vector_dim=config.embedding.dimension,
    distance=config.vectorstore.distance,
    api_key=config.vectorstore.api_key,
)
```

### 支持的文档格式

| 格式 | 扩展名 | 依赖 |
|------|--------|------|
| PDF | `.pdf` | pypdf |
| Word | `.docx`, `.doc` | python-docx |
| Excel | `.xlsx`, `.xls` | pandas（可选） |
| PowerPoint | `.pptx`, `.ppt` | python-pptx（可选） |
| CSV | `.csv` | 内置 |
| 文本 | `.txt`, `.md` | 内置 |

## 配置说明

### 配置加载顺序

1. `langchain_rag/.env`（优先）
2. 环境变量
3. `config/settings.py` 中的默认值

### 关键配置项（langchain_rag/.env）

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `DASHSCOPE_API_KEY` | 通义千问 API Key（必填） | - |
| `LLM_MODEL_NAME` | LLM 模型 | qwen3.6-plus |
| `EMBEDDING_MODEL_NAME` | Embedding 模型 | text-embedding-v3 |
| `EMBEDDING_DIMENSION` | Embedding 维度 | 1024 |
| `QDRANT_HOST` | Qdrant 地址（支持完整 URL） | localhost |
| `QDRANT_PORT` | Qdrant 端口 | 6333 |
| `QDRANT_COLLECTION_NAME` | 集合名称 | agent_rag_knowledge |
| `QDRANT_API_KEY` | Qdrant API Key（可选） | - |
| `QDRANT_DISTANCE` | 距离度量（COSINE/EUCLID/DOT/MANHATTAN） | COSINE |
| `RAG_CHUNK_SIZE` | 文档分块大小 | 512 |
| `RAG_CHUNK_OVERLAP` | 分块重叠 | 100 |
| `RAG_RETRIEVAL_TOP_K` | 检索结果数 | 10 |
| `AGENT_MAX_ITERATIONS` | Agent 最大迭代次数 | 10 |
| `AGENT_CONFIDENCE_THRESHOLD` | 置信度阈值 | 0.75 |

## 测试与验证

### 运行单元测试

```bash
# 全量测试
pytest -q

# 单模块测试
pytest langchain_rag/tests/test_qwen.py -q
pytest langchain_rag/tests/test_vectorstore.py -q
pytest langchain_rag/tests/test_processor.py -q
pytest langchain_rag/tests/test_agent_tools.py -q
```

### 冒烟测试（导入检查）

```bash
python test_imports.py
```

## 部署指南

### 开发环境

```bash
python start.py
```

### 生产环境

**使用 Gunicorn（Linux/macOS）：**
```bash
cd backend
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app \
    --bind 0.0.0.0:8000 \
    --access-logfile - \
    --error-logfile -
```

或使用提供的脚本：
```bash
bash start.sh prod
```

## 本项目已知易错点与最佳实践

| 易错点 | 说明 | 正确做法 |
|--------|------|----------|
| Qdrant Distance 枚举 | 必须用成员名（COSINE/EUCLID/DOT/MANHATTAN），不是值 | 全大写，用 `models.Distance[dist_upper]` |
| Qdrant Cloud URL | 不要填到 `host` + `port`，直接填完整 URL 到 `host` | `https://xxx.cloud.qdrant.io` |
| Qwen API Key | `Generation.call()` 必须显式传 `api_key` | `gen_kwargs["api_key"] = self.api_key` |
| AIMessage tool_calls | 不要传 `None`，只在有工具调用时才传此字段 | `if tool_calls: ai_message_kwargs["tool_calls"] = tool_calls` |
| 配置读取 | `os.getenv()` 读不到 `.env`，需先加载到 `os.environ` | `settings.py` 已自动处理 |
| Embedding 维度 | `text-embedding-v3` = 1024，`text-embedding-v2` = 1536 | 与 Qdrant 集合保持一致，不匹配时重建 |
| PYTHONPATH | 必须包含项目根目录和 `langchain_rag/` | 启动脚本已自动设置 |

## 故障排查

### 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| API 返回 401 / Invalid API key | `DASHSCOPE_API_KEY` 错误或未传递 | 检查 `.env` 并确认 `Generation.call` 收到该参数 |
| Qdrant 连接失败 | Host/Port/API Key 错误 | 确认 `QDRANT_HOST`（Cloud 时用完整 URL）和 `QDRANT_API_KEY` |
| `Wrong input: Vector dimension error` | Embedding 维度与集合不一致 | 换匹配的 embedding 模型，或用 `ingest_docs.py` 自动重建 |
| `KeyError: 'tool_calls'` | DashScope 响应访问方式不对 | 用 `"tool_calls" in message` 而非 `hasattr()` |
| 文档解析失败 | 缺少对应解析库 | 安装：`pip install pypdf python-docx` |

### 配置检查工具

```bash
python check_config.py
```

### 日志查看

```bash
# 后端日志
python start.py 2>&1 | tee backend.log
```

## 许可证

MIT License

---

**注意**：本项目仅供内部使用，所有数据操作严格遵循公司信息安全管理制度，确保 proprietary 知识不流出企业边界。
