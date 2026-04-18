# Agentic RAG - 智能工业知识系统

## 目录

1. [项目简介](#项目简介)
2. [系统架构](#系统架构)
3. [技术栈详解](#技术栈详解)
4. [快速开始](#快速开始)
5. [MinerU 文档解析集成](#mineru-文档解析集成)
6. [配置详解](#配置详解)
7. [API 文档](#api-文档)
8. [知识库管理](#知识库管理)
9. [测试与验证](#测试与验证)
10. [部署指南](#部署指南)
11. [故障排查](#故障排查)
12. [最佳实践](#最佳实践)

---

## 项目简介

### 项目背景

Agentic RAG 是**广东迪奥技术有限公司**为国家级专精特新"小巨人"企业打造的 AI 总工程师工具体系，聚焦 PCB 厂务 / HVAC（中央空调）领域的知识管理、投标报价复核和技术合规审核。

**解决的核心痛点**：
- **知识沉淀困境**：20 年 PCB 厂务经验分散在个人电脑与纸质档案中，新人培养周期长
- **投标响应瓶颈**：单个智慧低碳项目招标书平均 200 页，技术合规审核耗时 3-5 天
- **报价精准度风险**：中央空调系统涉及 200+ 分项报价，曾出现漏算亏损案例
- **数据安全红线**：厂务数据涉及客户产线机密，传统 SaaS AI 工具无法通过安全审计

**建设目标**：1 个月内完成空调领域最小可行 Demo（MVP），实现知识复用率提升 50%、投标审核效率提升 50%、报价复核准确率 100%。

### 核心功能

| 功能模块 | 说明 | 状态 |
|---------|------|------|
| **知识问答** | 基于 RAG 技术的智能问答系统，支持专业术语理解 | ✅ |
| **报价复核** | 硬逻辑校验防止 LLM 幻觉，确保报价准确性 | ✅ |
| **合规审核** | 自动检查投标方案的技术合规性 | ✅ |
| **MinerU 文档解析** | 支持复杂版式 PDF（合并单元格、跨页表格、公式）解析 | ✅ Phase 2 |
| **长短期记忆** | 支持多轮对话，提供连续上下文理解 | ✅ |
| **智能路由** | 自动识别用户意图，调用相应工具 | ✅ |
| **Human-in-the-Loop** | 低置信度时自动触发人工审核 | ✅ |

---

## 系统架构

### 四层增强架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    【交互管控层】Interface Layer                       │
│   内部API网关 │ Web管理后台 │ 人工干预入口 │ 审计日志              │
├─────────────────────────────────────────────────────────────────────┤
│                    【业务引擎层】Agent Layer                           │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │           LangGraph 智能体状态机 (ReAct Pattern)               │  │
│  │ 意图识别 → 工具路由 → 执行监控 → 质量评估 → [置信度检查]      │  │
│  │                   ↓ 置信度<0.75或3次失败                       │  │
│  │              【人工Fallback节点】→ 审核队列 → 知识回流        │  │
│  └───────────────────────────────────────────────────────────────┘  │
├──────────────┬──────────────────┬──────────────────┬───────────────┤
│ 【P1】知识问答 │ 【P2】报价复核     │ 【P3】合规审核      │ 【Eval】评估 │
│ RAG Engine   │ Quote Validator  │ Compliance Agent │ RAGAS+黄金集  │
├──────────────┴──────────────────┴──────────────────┴───────────────┤
│                    【数据智能层】Data Intelligence                     │
│   Qdrant向量库 │ MinerU文档解析 │ 历史报价库 │ 知识库版本控制      │
├─────────────────────────────────────────────────────────────────────┤
│                    【推理引擎层】Inference Engine                    │
│   Qwen LLM (通义千问) │ DashScope Embeddings                        │
├─────────────────────────────────────────────────────────────────────┤
│                    【基础设施层】Infrastructure                        │
│   Docker 容器化 │ 本地部署 │ 数据物理隔离 │ 备份策略              │
└─────────────────────────────────────────────────────────────────────┘
```

### 核心工作流

#### 文档灌库流程

```
文档上传 → MinerU/标准解析 → 质量检测 → 路径元数据提取 → 
表格感知分块 → 向量化 → Qdrant 存储
```

#### RAG 查询流程

```
用户 Query → Query 重写（术语扩展）→ 向量检索（Top 10）→
重排序（Rerank）→ Top 5 精选 → 上下文组装 → LLM 生成 →
RAGAS 实时评估 → 输出 + 置信度标签
```

---

## 技术栈详解

### 核心技术选型

| 层级 | 技术 | 版本 | 选型理由 |
|------|------|------|----------|
| **后端框架** | FastAPI | >=0.104.0 | 高性能异步框架，自动生成 API 文档 |
| **LLM** | 通义千问 (Qwen) | qwen3.6-plus / qwen-plus | 中文工业术语理解顶尖，商业许可友好 |
| **Embedding** | 通义千问 | text-embedding-v3 | 1024 维，中文优化 |
| **向量库** | Qdrant | >=1.7.0 | 亚秒级检索，支持 Payload 过滤，权限管控完善 |
| **文档解析** | MinerU (主) + pypdf (备) | - | MinerU 完美处理合并单元格与嵌套表格，输出 Markdown |
| **Agent 框架** | LangChain + LangGraph | 1.0.8 / 1.0.10 | 支持复杂状态机与 Human-in-the-Loop，工具调用生态成熟 |
| **文档解析** | pypdf / python-docx | - | PDF/DOCX 标准解析 |

### 依赖版本管理

本项目使用精确的依赖版本以确保稳定性：

| 依赖包 | 版本 | 用途 |
|--------|------|------|
| `langchain` | 1.0.8 | 智能链管理 |
| `langchain-core` | 1.3.0 | 核心抽象层 |
| `langchain-classic` | 1.0.3 | 经典组件 |
| `langgraph` | 1.0.10 | Agent 状态机 |
| `qdrant-client` | >=1.7.0 | Qdrant 客户端 |
| `pypdf` | >=3.0.0 | PDF 解析 |
| `python-docx` | >=0.8.11 | DOCX 解析 |
| `dashscope` | >=1.0.0 | 通义千问 SDK |
| `fastapi` | >=0.104.0 | 后端框架 |
| `uvicorn` | >=0.24.0 | ASGI 服务器 |

---

## 快速开始

### 1. 环境要求

**系统要求：**
- Python 3.8 - 3.11
- 操作系统：Windows 10+ / macOS 10.15+ / Linux (Ubuntu 20.04+)
- 内存：建议 16GB+
- 磁盘：至少 10GB 可用空间

**推荐使用 Conda 环境：**
```bash
# 创建 conda 环境
conda create -n agent_rag python=3.10
conda activate agent_rag
```

### 2. 安装依赖

```bash
# 克隆项目
cd agent_rag

# 安装全量依赖（推荐）
pip install -r requirements.txt

# 或分模块安装（仅核心模块）
pip install -r langchain_rag/requirements.txt
```

**验证安装：**
```bash
python test_imports.py
```

### 3. 配置环境变量

**关键说明**：配置文件优先使用 `langchain_rag/.env`（而非 `backend/.env`）。

#### 步骤 1：从示例创建配置

```bash
cp langchain_rag/.env.example langchain_rag/.env
```

#### 步骤 2：编辑配置文件

编辑 `langchain_rag/.env`，以下是完整配置说明：

```env
# ==========================================
# 通义千问 API 配置（必填）
# ==========================================
# 获取地址：https://dashscope.console.aliyun.com/
DASHSCOPE_API_KEY=sk-293f8466de904dda8784bb53bf08fde0

# ==========================================
# LLM 配置
# ==========================================
LLM_PROVIDER=qwen
# 可选模型：qwen3.6-plus / qwen-plus / qwen-turbo
LLM_MODEL_NAME=qwen3.6-plus
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=2048

# ==========================================
# Embedding 配置
# ==========================================
# text-embedding-v3: 1024 维（推荐，新集合）
# text-embedding-v2: 1536 维（兼容旧集合）
EMBEDDING_MODEL_NAME=text-embedding-v3
EMBEDDING_DIMENSION=1024

# ==========================================
# Qdrant 向量库配置
# ==========================================
# Cloud 版本：完整 URL（推荐）
QDRANT_HOST=https://d13507c3-27ff-41ce-9ae3-2a3fab84e199.eu-west-2-0.aws.cloud.qdrant.io
QDRANT_PORT=6334
QDRANT_COLLECTION_NAME=lmf_v1
QDRANT_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# 本地版本：
# QDRANT_HOST=localhost
# QDRANT_PORT=6333
# QDRANT_API_KEY=

# 距离度量：COSINE / EUCLID / DOT / MANHATTAN
QDRANT_DISTANCE=COSINE

# ==========================================
# RAG 配置
# ==========================================
RAG_CHUNK_SIZE=512
RAG_CHUNK_OVERLAP=100
RAG_RETRIEVAL_TOP_K=10
RAG_RERANK_TOP_K=5
RAG_MIN_RELEVANCE_SCORE=0.75

# ==========================================
# Agent 配置
# ==========================================
AGENT_MAX_ITERATIONS=10
AGENT_CONFIDENCE_THRESHOLD=0.75
AGENT_FALLBACK_TO_HUMAN=true

# ==========================================
# MinerU 文档解析配置（Phase 2）
# ==========================================
# 是否启用 MinerU（启用后 PDF 优先用 MinerU 解析）
MINERU_ENABLED=false
# MinerU API 服务地址
MINERU_API_BASE=http://localhost:8008
# API Key（如需要）
MINERU_API_KEY=
# 请求超时时间（秒）
MINERU_TIMEOUT=300
# 输出格式：markdown / json
MINERU_OUTPUT_FORMAT=markdown
# 是否启用 OCR（扫描件需要）
MINERU_ENABLE_OCR=false
# 是否启用公式识别
MINERU_ENABLE_FORMULA=true
# 是否启用表格识别
MINERU_ENABLE_TABLE=true
```

### 4. 启动 Qdrant（如使用本地版本）

#### 方式 A：使用 Docker（推荐）

```bash
docker run -d \
  -p 6333:6333 \
  -p 6334:6334 \
  -v $(pwd)/qdrant_data:/qdrant/storage \
  qdrant/qdrant:v1.7.0
```

#### 方式 B：使用 Qdrant Cloud（无需本地部署）

1. 注册：https://cloud.qdrant.io/
2. 创建免费集群
3. 获取 Host、Port、API Key 填入 `.env`

### 5. 文档灌库

将你的文档放入 `data/` 目录，支持子文件夹结构。

**推荐的文件夹结构：**
```
data/
├── 技术规范/
│   ├── 中央空调/
│   │   ├── 设计手册.pdf
│   │   └── 技术参数表.pdf
│   └── 冷水机组/
│       └── 选型标准.docx
├── 操作手册/
│   └── 维护指南/
│       └── 日常巡检.txt
└── 报价模板/
    └── 设备清单模板.xlsx
```

**运行灌库脚本：**

```bash
# Windows
set PYTHONPATH=%CD%;%CD%\langchain_rag
python ingest_docs.py

# Linux/macOS
export PYTHONPATH=$(pwd):$(pwd)/langchain_rag
python ingest_docs.py
```

**ingest_docs.py 功能说明：**
- ✅ 自动递归扫描 `data/` 下所有子文件夹
- ✅ 文件夹层级自动作为元数据：`category` / `subcategory` / `folder_path`
- ✅ 高级路径元数据提取：`project_name` / `brand` / `model_spec`
- ✅ 质量检测：扫描件/乱码/加密/格式黑名单自动识别
- ✅ MinerU 优先：PDF 优先用 MinerU 解析，失败自动回退 PyPDF
- ✅ 表格感知分块：整表保留，普通文本按语义分块
- ✅ 自动检测 embedding 维度与 Qdrant 集合匹配，不匹配时自动删旧重建
- ✅ 详细日志输出到 `ingest_docs.log`
- ✅ 实时进度条显示

### 6. 启动服务

#### 一键启动（推荐）

```bash
python start.py
```

#### 分别启动

**仅启动后端（开发模式，带 reload）：**
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

### 7. 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| **前端界面** | http://localhost:3000 | Web 交互界面 |
| **后端 API** | http://localhost:8000 | FastAPI 后端 |
| **API 文档** | http://localhost:8000/docs | Swagger UI |
| **API 文档（备选）** | http://localhost:8000/redoc | ReDoc |
| **Qdrant 控制台** | https://cloud.qdrant.io/ | Cloud 版本管理 |

---

## MinerU 文档解析集成

### 什么是 MinerU

MinerU 是阿里云开源的专业文档解析工具，专门针对复杂版式 PDF（含合并单元格、跨页表格、公式等）设计，输出 Markdown 格式，完美适合 LLM 理解。

**MinerU 的优势：**
- ✅ 智能还原合并单元格
- ✅ 自动合并跨页表格
- ✅ 原生输出 Markdown 格式
- ✅ 公式识别导出 LaTeX
- ✅ 支持 OCR 扫描件

### MinerU 部署方式

#### Phase 2：API 接口调用（当前）

当前阶段使用 HTTP REST API 调用 MinerU 服务，你可以：
1. 部署自己的 MinerU API 服务
2. 使用第三方 MinerU 云服务

#### 后续 Phase 3：Docker 本地部署

后续将支持 Docker Compose 一键部署 MinerU 本地服务。

### MinerU 配置详解

在 `langchain_rag/.env` 中配置：

```env
# 启用 MinerU
MINERU_ENABLED=true

# MinerU API 地址
MINERU_API_BASE=http://localhost:8008

# API Key（如服务需要）
MINERU_API_KEY=your-api-key-if-needed

# 超时时间（秒），大文件需要更长时间
MINERU_TIMEOUT=300

# 输出格式：markdown（推荐）或 json
MINERU_OUTPUT_FORMAT=markdown

# 是否启用 OCR（仅扫描件需要，会增加耗时）
MINERU_ENABLE_OCR=false

# 是否启用公式识别
MINERU_ENABLE_FORMULA=true

# 是否启用表格识别
MINERU_ENABLE_TABLE=true
```

### MinerU API 协议

MinerUClient 使用的 HTTP API 协议：

#### 健康检查

```
GET /health
```

**响应示例：**
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

#### 文档解析

```
POST /parse
Content-Type: multipart/form-data

file: [PDF 文件]
output_format: markdown | json
enable_ocr: true | false
enable_formula: true | false
enable_table: true | false
```

**响应示例：**
```json
{
  "success": true,
  "markdown": "# 文档标题\n\n## 章节内容\n\n| 列1 | 列2 |\n|-----|-----|\n| 值1 | 值2 |",
  "page_count": 10,
  "table_count": 3,
  "parse_time_seconds": 5.2
}
```

### 回退机制

系统采用智能回退策略：

```
尝试 MinerU → 成功 → 使用 MinerU 结果
    ↓ 失败
尝试 PyPDF → 成功 → 使用 PyPDF 结果
    ↓ 失败
跳过该文件并记录警告
```

**MinerU 失败的情况：**
- MinerU 服务未启用（`MINERU_ENABLED=false`）
- MinerU 服务连接失败
- MinerU 解析超时
- MinerU 返回错误

### 使用建议

| 文档类型 | MinerU | PyPDF | 说明 |
|---------|--------|-------|------|
| 简单技术文档 | ✅ | ✅ | 都可以，PyPDF 更快 |
| 带复杂表格的招标书 | ✅ 优先 | ⚠️ | MinerU 能正确处理合并单元格 |
| 带公式的技术手册 | ✅ 优先 | ❌ | MinerU 能识别公式 |
| 扫描件 PDF | ✅（需 OCR） | ❌ | 启用 OCR 后 MinerU 可处理 |
| 简单文本 PDF | ⚠️ 可选 | ✅ 优先 | PyPDF 更快更稳定 |

---

## 配置详解

### 配置加载顺序

配置按以下优先级加载（高优先级覆盖低优先级）：

1. **`langchain_rag/.env`**（最高优先级）
2. **系统环境变量**
3. **`langchain_rag/config/settings.py` 中的默认值**

### 配置类详解

配置使用 Pydantic v2 管理，所有配置类位于 `langchain_rag/config/settings.py`。

#### LLMConfig（LLM 配置）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `provider` | Literal["qwen", "openai", "anthropic"] | "qwen" | LLM 提供商 |
| `model_name` | str | "qwen-plus" | 模型名称 |
| `api_key` | str | "" | API Key |
| `api_base` | str | "https://dashscope.aliyuncs.com/compatible-mode/v1" | API 地址 |
| `temperature` | float | 0.7 | 采样温度 |
| `max_tokens` | int | 2048 | 最大生成 Token 数 |
| `timeout` | int | 120 | 超时时间（秒） |

#### EmbeddingConfig（Embedding 配置）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `provider` | Literal["qwen", "openai", "local"] | "qwen" | Embedding 提供商 |
| `model_name` | str | "text-embedding-v3" | 模型名称 |
| `api_key` | str | "" | API Key |
| `api_base` | str | "https://dashscope.aliyuncs.com/compatible-mode/v1" | API 地址 |
| `dimension` | int | 1536 | 向量维度 |

**注意：** `text-embedding-v3` 是 1024 维，`text-embedding-v2` 是 1536 维。

#### VectorStoreConfig（向量库配置）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `provider` | Literal["qdrant", "chroma", "milvus"] | "qdrant" | 向量库提供商 |
| `host` | str | "localhost" | 主机地址（支持完整 URL） |
| `port` | int | 6333 | 端口 |
| `collection_name` | str | "agent_rag_knowledge" | 集合名称 |
| `vector_dim` | int | 1536 | 向量维度 |
| `distance` | Literal["COSINE", "EUCLID", "DOT", "MANHATTAN"] | "COSINE" | 距离度量 |
| `api_key` | str | "" | API Key |

**重要：** 使用 Qdrant Cloud 时，`host` 填完整 URL（如 `https://xxx.cloud.qdrant.io`），不要拆成 host + port。

#### RAGConfig（RAG 配置）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `chunk_size` | int | 512 | 文档分块大小 |
| `chunk_overlap` | int | 100 | 分块重叠 |
| `retrieval_top_k` | int | 10 | 检索结果数 |
| `rerank_top_k` | int | 5 | 重排序后结果数 |
| `min_relevance_score` | float | 0.75 | 最小相关度阈值 |

#### MinerUConfig（MinerU 配置）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | bool | false | 是否启用 |
| `api_base` | str | "http://localhost:8008" | API 地址 |
| `api_key` | str | "" | API Key |
| `timeout` | int | 300 | 超时时间（秒） |
| `max_file_size_mb` | int | 50 | 最大文件大小（MB） |
| `output_format` | Literal["markdown", "json"] | "markdown" | 输出格式 |
| `enable_ocr` | bool | false | 是否启用 OCR |
| `enable_formula` | bool | true | 是否启用公式识别 |
| `enable_table` | bool | true | 是否启用表格识别 |

### 配置检查工具

项目提供配置检查工具：

```bash
python check_config.py
```

该工具会检查：
- ✅ `.env` 文件是否存在
- ✅ 必填配置项是否已设置
- ✅ API Key 格式是否正确
- ✅ Qdrant 连接是否正常
- ✅ Embedding 维度与模型是否匹配

---

## API 文档

### 核心 API 端点

| 端点 | 方法 | 功能 | 认证 |
|------|------|------|------|
| `/health` | GET | 健康检查 | 否 |
| `/api/rag/query` | POST | RAG 知识查询 | 否 |
| `/api/agent/invoke` | POST | Agent 工作流执行 | 否 |
| `/api/memory/operation` | POST | 记忆操作（get/clear/save） | 否 |
| `/api/memory/sessions` | GET | 列出会话 | 否 |
| `/api/agent/tools` | GET | 可用工具列表 | 否 |

### 示例请求

#### RAG 查询

```http
POST /api/rag/query
Content-Type: application/json

{
  "query": "中央空调系统的 COP 值一般是多少？",
  "session_id": "session_123456",
  "top_k": 5
}
```

**响应示例：**
```json
{
  "success": true,
  "answer": "中央空调系统的 COP（能效比）一般在 5.0-6.0 左右...",
  "sources": [
    {
      "source": "data/技术规范/中央空调/设计手册.pdf",
      "page": 15,
      "content": "COP（能效比）是指制冷量与输入功率的比值..."
    }
  ],
  "confidence": 0.92
}
```

#### Agent 调用

```http
POST /api/agent/invoke
Content-Type: application/json

{
  "query": "请帮我复核这份报价",
  "session_id": "session_123456",
  "stream": false
}
```

#### 记忆操作

```http
POST /api/memory/operation
Content-Type: application/json

{
  "operation": "get",
  "session_id": "session_123456"
}
```

支持的操作：
- `get`：获取会话记忆
- `clear`：清除会话记忆
- `save`：保存会话记忆

---

## 知识库管理

### 文档灌库（推荐方式）

使用 `ingest_docs.py` 是最简单、最完整的灌库方式，详见前文"快速开始 - 5. 文档灌库"。

### 手动灌库（高级）

如果你需要更精细的控制，直接使用底层函数：

```python
from langchain_rag.document.processor import (
    DocumentProcessor,
    ChunkConfig,
    DocumentMetadata,
)
from langchain_rag.document.quality_checker import QualityChecker
from langchain_rag.vectorstore.qdrant import QdrantVectorStore, DashScopeEmbeddings
from langchain_rag.config.settings import config

# 1. 创建文档处理器
processor = DocumentProcessor(
    chunk_config=ChunkConfig(
        chunk_size=config.rag.chunk_size,
        chunk_overlap=config.rag.chunk_overlap,
    ),
    use_mineru=config.mineru.enabled,
)

# 2. 加载文档
docs = processor.load_document(
    "data/技术规范/中央空调/设计手册.pdf",
    metadata=DocumentMetadata.from_path_advanced(
        "data/技术规范/中央空调/设计手册.pdf",
        "data"
    )
)

# 3. 切分文档
split_docs = processor.split_documents(docs)

# 4. 存入 Qdrant
embeddings = DashScopeEmbeddings(
    model_name=config.embedding.model_name,
    api_key=config.embedding.effective_api_key,
)
vectorstore = QdrantVectorStore.from_documents(
    documents=split_docs,
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

| 格式 | 扩展名 | 依赖 | MinerU 支持 |
|------|--------|------|-------------|
| PDF | `.pdf` | pypdf | ✅ |
| Word | `.docx`, `.doc` | python-docx | ❌ |
| Excel | `.xlsx`, `.xls` | pandas（可选） | ❌ |
| PowerPoint | `.pptx`, `.ppt` | python-pptx（可选） | ❌ |
| CSV | `.csv` | 内置 | ❌ |
| 文本 | `.txt`, `.md` | 内置 | ❌ |

### 文件夹元数据提取

系统支持从文件夹路径自动提取元数据，基于以下目录结构：

```
data/{project_name}/{doc_type}/{equipment_category}/{brand}/{filename}
```

**示例路径：**
```
data/珠海深联高效机房资料20241024/EQP-设备技术资料/EQP-01 冷水机组/特灵---10-22/CCTV - CCTV-1650RT-6.45 - Product Report.pdf
```

**自动提取的元数据：**
```python
{
    "project_name": "珠海深联高效机房",
    "doc_type": "设备技术资料",
    "equipment_category": "冷水机组",
    "brand": "特灵",
    "model_spec": "CCTV-1650RT-6.45",
    "file_type_tag": "Product Report",
    "folder_path": "珠海深联高效机房资料20241024/EQP-设备技术资料/EQP-01 冷水机组/特灵---10-22"
}
```

---

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

# 详细输出
pytest -v
```

### 冒烟测试（导入检查）

```bash
python test_imports.py
```

### MinerU 测试

如果你配置了 MinerU，可以测试 MinerU 集成：

```python
from langchain_rag.document.mineru_client import create_mineru_client_from_config
from langchain_rag.document.mineru_loader import MinerULoader

# 1. 检查 MinerU 服务
client = create_mineru_client_from_config()
if client:
    print("MinerU client created")
    print(f"Health check: {client.health_check()}")

    # 2. 测试解析
    loader = MinerULoader("test.pdf", client=client)
    docs = loader.load()
    print(f"Loaded {len(docs)} documents")
```

---

## 部署指南

### 开发环境

```bash
python start.py
```

开发环境特点：
- ✅ 自动 reload（代码修改后自动重启）
- ✅ 详细日志输出
- ✅ 调试友好

### 生产环境

#### 使用 Gunicorn（Linux/macOS）

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

#### 使用 systemd（Linux）

创建 `/etc/systemd/system/agent-rag.service`：

```ini
[Unit]
Description=Agentic RAG Service
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/opt/agent_rag
Environment="PATH=/opt/conda/envs/agent_rag/bin"
ExecStart=/opt/conda/envs/agent_rag/bin/python start.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable agent-rag
sudo systemctl start agent-rag
sudo systemctl status agent-rag
```

#### Windows 服务（使用 NSSM）

```cmd
# 下载 NSSM: https://nssm.cc/
nssm install AgentRAG
nssm start AgentRAG
```

### Docker 部署

#### 构建镜像

```bash
docker build -t agent-rag:latest .
```

#### 运行容器

```bash
docker run -d \
  -p 8000:8000 \
  -p 3000:3000 \
  -v $(pwd)/langchain_rag/.env:/app/langchain_rag/.env \
  -v $(pwd)/data:/app/data \
  --name agent-rag \
  agent-rag:latest
```

#### Docker Compose（推荐）

创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:v1.7.0
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage

  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - QDRANT_HOST=http://qdrant:6333
    volumes:
      - ./langchain_rag/.env:/app/langchain_rag/.env
      - ./data:/app/data
    depends_on:
      - qdrant

volumes:
  qdrant_data:
```

启动：

```bash
docker-compose up -d
```

---

## 故障排查

### 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| **API 返回 401 / Invalid API key** | `DASHSCOPE_API_KEY` 错误或未传递 | 检查 `.env` 并确认 `Generation.call` 收到该参数 |
| **Qdrant 连接失败** | Host/Port/API Key 错误 | 确认 `QDRANT_HOST`（Cloud 时用完整 URL）和 `QDRANT_API_KEY` |
| **`Wrong input: Vector dimension error`** | Embedding 维度与集合不一致 | 换匹配的 embedding 模型，或用 `ingest_docs.py` 自动重建 |
| **`KeyError: 'tool_calls'`** | DashScope 响应访问方式不对 | 用 `"tool_calls" in message` 而非 `hasattr()` |
| **文档解析失败** | 缺少对应解析库 | 安装：`pip install pypdf python-docx` |
| **MinerU 连接失败** | MinerU 服务未启动或地址错误 | 检查 `MINERU_API_BASE`，确认服务正在运行 |
| **ingest_docs.py 卡住** | 大文件解析超时 | 增加 `MINERU_TIMEOUT`，或临时禁用 MinerU |
| **导入错误 `No module named 'xxx'`** | 依赖未安装或 PYTHONPATH 错误 | 安装依赖，确认 PYTHONPATH 包含项目根目录 |

### Qdrant 相关问题

#### 问题 1：集合已存在但维度不匹配

**错误信息：**
```
Wrong input: Vector dimension 1024, expected 1536
```

**解决方案：**
使用 `ingest_docs.py`，它会自动检测并重建集合，或手动删除：

```python
from langchain_rag.vectorstore.qdrant import QdrantVectorStore
from langchain_rag.config.settings import config

vectorstore = QdrantVectorStore(
    host=config.vectorstore.host,
    port=config.vectorstore.port,
    collection_name=config.vectorstore.collection_name,
    api_key=config.vectorstore.api_key,
)
vectorstore.delete_collection()
```

#### 问题 2：Qdrant Cloud 连接失败

**错误信息：**
```
Connection refused
```

**解决方案：**
确认 `QDRANT_HOST` 填的是完整 URL，不要拆分 host + port：

```env
# ❌ 错误
QDRANT_HOST=d13507c3-27ff-41ce-9ae3-2a3fab84e199.eu-west-2-0.aws.cloud.qdrant.io
QDRANT_PORT=6334

# ✅ 正确
QDRANT_HOST=https://d13507c3-27ff-41ce-9ae3-2a3fab84e199.eu-west-2-0.aws.cloud.qdrant.io
QDRANT_PORT=6334
```

### MinerU 相关问题

#### 问题 1：MinerU 服务不可用

**错误信息：**
```
MinerU connection failed to http://localhost:8008
```

**解决方案：**
1. 检查 `MINERU_ENABLED` 是否为 `true`
2. 确认 MinerU 服务正在运行
3. 检查 `MINERU_API_BASE` 地址是否正确
4. 或者临时禁用 MinerU，使用 PyPDF

#### 问题 2：MinerU 解析超时

**错误信息：**
```
MinerU parse timeout after 300s
```

**解决方案：**
1. 增加 `MINERU_TIMEOUT`（如 600）
2. 检查文件是否过大（>50MB）
3. 临时禁用 MinerU 处理该文件

### 日志查看

**后端日志：**
```bash
python start.py 2>&1 | tee backend.log
```

**ingest_docs 日志：**
```bash
tail -f ingest_docs.log
```

### 配置检查

```bash
python check_config.py
```

---

## 最佳实践

### 本项目已知易错点

| 易错点 | 说明 | 正确做法 |
|--------|------|----------|
| Qdrant Distance 枚举 | 必须用成员名（COSINE/EUCLID/DOT/MANHATTAN），不是值 | 全大写，用 `models.Distance[dist_upper]` |
| Qdrant Cloud URL | 不要填到 `host` + `port`，直接填完整 URL 到 `host` | `https://xxx.cloud.qdrant.io` |
| Qwen API Key | `Generation.call()` 必须显式传 `api_key` | `gen_kwargs["api_key"] = self.api_key` |
| AIMessage tool_calls | 不要传 `None`，只在有工具调用时才传此字段 | `if tool_calls: ai_message_kwargs["tool_calls"] = tool_calls` |
| 配置读取 | `os.getenv()` 读不到 `.env`，需先加载到 `os.environ` | `settings.py` 已自动处理 |
| Embedding 维度 | `text-embedding-v3` = 1024，`text-embedding-v2` = 1536 | 与 Qdrant 集合保持一致，不匹配时重建 |
| PYTHONPATH | 必须包含项目根目录和 `langchain_rag/` | 启动脚本已自动设置 |
| MinerU 配置 | 启用后确认服务可用，否则会回退但增加耗时 | 生产环境确认 MinerU 稳定后再启用 |

### 知识库管理最佳实践

1. **文件夹结构规范**
   - 按项目/文档类型/设备分类组织
   - 文件夹名称使用清晰的命名
   - 日期后缀会自动去除（如 `资料20241024` → `资料`）

2. **文档预处理**
   - 优先使用可编辑格式（DOCX、XLSX）而非扫描件
   - 扫描件需要启用 OCR（`MINERU_ENABLE_OCR=true`）
   - 超大文件（>50MB）建议拆分

3. **分块大小选择**
   - 技术文档：512-1024 字符
   - 表格密集文档：256-512 字符
   - 简单文本：1024-2048 字符

4. **灌库流程**
   - 先小批量测试（10-20 份文档）
   - 验证元数据提取正确
   - 检查切片质量
   - 再全量灌库

### 性能优化

1. **Embedding 批量处理**
   - `ingest_docs.py` 已默认批量 50 个文档
   - 可根据内存调整 `batch_size`

2. **Qdrant 索引优化**
   - 数据量 < 10 万：默认配置即可
   - 数据量 > 10 万：考虑 HNSW 索引参数调优

3. **MinerU 使用策略**
   - 只对复杂表格/公式文档启用
   - 简单文档用 PyPDF 更快
   - 可按文件夹选择性启用

### 安全建议

1. **API Key 管理**
   - 不要将 `.env` 提交到 Git
   - 使用环境变量或密钥管理系统
   - 定期轮换 API Key

2. **数据隔离**
   - 生产环境使用本地部署
   - 禁止数据公网传输
   - 定期备份 Qdrant 数据

3. **访问控制**
   - Qdrant 使用 API Key 认证
   - 后端添加认证中间件
   - 记录操作日志

---

## 项目文件结构

```
agent_rag/
├── langchain_rag/              # 核心 RAG & Agent 库
│   ├── agent/                  # Agent 状态机（LangGraph）
│   │   └── core.py            # AgenticRAGAgent / ReActAgent
│   ├── config/                 # 配置管理
│   │   └── settings.py        # Pydantic v2 配置（统一入口）
│   ├── document/               # 文档加载与处理
│   │   ├── processor.py       # 多格式加载 + 中文优化分块
│   │   ├── quality_checker.py # 文档质量检测
│   │   ├── mineru_client.py   # ✨ MinerU API 客户端（Phase 2）
│   │   └── mineru_loader.py   # ✨ MinerU 文档加载器（Phase 2）
│   ├── examples/               # 使用示例
│   │   └── quickstart.py      # 完整示例
│   ├── llm/                    # LLM 集成
│   │   └── qwen.py            # ChatQwen + Function Calling
│   ├── rag/                    # 检索链
│   │   └── retrieval.py       # AdvancedRAGChain / ConversationalRAGChain
│   ├── tools/                  # Agent 工具集
│   │   └── agent_tools.py     # KnowledgeRetrieval / QuoteValidation / ComplianceCheck
│   ├── vectorstore/            # 向量存储
│   │   └── qdrant.py          # QdrantVectorStore + DashScopeEmbeddings
│   ├── tests/                  # 单元测试
│   │   ├── conftest.py
│   │   ├── test_qwen.py
│   │   ├── test_vectorstore.py
│   │   ├── test_processor.py
│   │   └── test_agent_tools.py
│   ├── .env                    # 环境配置（不提交 Git）
│   └── .env.example            # 环境配置示例
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
│   ├── 技术规范/
│   ├── 操作手册/
│   └── 报价模板/
├── docs/                        # 文档
│   └── superpowers/
│       └── plans/
├── doc/                         # 技术文档
│   └── 文档预处理技术路线讨论.md
├── ingest_docs.py               # ✨ 文档灌库脚本（递归 + 文件夹元数据）
├── start.py                     # 一键启动脚本
├── start.sh                     # Linux/macOS 启动
├── start.bat                    # Windows 启动
├── gunicorn_conf.py             # 生产环境 Gunicorn 配置
├── requirements.txt             # 全量依赖
├── langchain_rag/requirements.txt
├── backend/requirements.txt
├── check_config.py              # 配置检查工具
├── test_imports.py              # 导入测试
├── CLAUDE.md                    # Claude Code 协作规范
├── 技术方案书v1.0.md            # 原始技术方案
├── .gitignore
└── README.md                    # 本文档
```

---

## 许可证

MIT License

---

## 联系方式与支持

**项目维护**：广东迪奥技术有限公司 AI 总工程师团队

**问题反馈**：
- 提交 Issue
- 查看 `ingest_docs.log` 日志
- 运行 `check_config.py` 检查配置

---

**注意**：本项目仅供内部使用，所有数据操作严格遵循公司信息安全管理制度，确保 proprietary 知识不流出企业边界。
