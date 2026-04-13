# Agentic RAG - 智能工业知识系统

## 项目简介

Agentic RAG是一个基于LangChain和FastAPI的智能工业知识系统，专注于PCB厂务领域的知识管理、投标报价复核和技术合规审核。系统采用本地部署架构，确保数据安全可控。

### 核心功能

- **知识问答**：基于RAG技术的智能问答系统，支持专业术语理解
- **报价复核**：硬逻辑校验防止LLM幻觉，确保报价准确性
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
│ ├── 业务服务                                   │
│ └── 记忆管理                                   │
├─────────────────────────────────────────────────┤
│ 核心层 (LangChain + Agent)                     │
│ ├── RAG引擎                                    │
│ ├── Agent状态机                                │
│ └── 工具集                                     │
├─────────────────────────────────────────────────┤
│ 存储层 (Qdrant + Redis/SQLite)                │
└─────────────────────────────────────────────────┘
```

### 技术栈

| 类别 | 技术 | 版本 | 用途 |
|------|------|------|------|
| **后端框架** | FastAPI | >=0.104.0 | API服务 |
| **LLM** | 通义千问 (Qwen) | - | 智能推理 |
| **向量库** | Qdrant | >=1.7.0 | 知识存储 |
| **记忆存储** | Redis/内存 | - | 会话管理 |
| **前端** | HTML + Tailwind CSS | - | 交互界面 |
| **LangChain** | langchain | >=0.1.0 | 智能链管理 |

## 快速开始

### 1. 环境要求

- Python 3.8+  
- Qdrant 1.7.0+  
- Redis 6.0+ (可选，用于会话存储)  
- 通义千问API Key  

### 2. 安装依赖

```bash
# 1. 克隆项目
git clone <repository-url>
cd agent_rag

# 2. 安装核心RAG模块依赖
cd langchain_rag
pip install -r requirements.txt
cd ..

# 3. 安装后端依赖
cd backend
pip install -r requirements.txt
cd ..
```

### 3. 配置环境变量

编辑 `backend/.env` 文件：

```env
# API Settings
API_HOST=0.0.0.0
API_PORT=8000

# Database Settings
DATABASE_URL=sqlite:///./agent_rag.db

# Redis Settings (for session storage)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Memory Settings
MEMORY_TYPE=inmemory  # inmemory or redis
MEMORY_MAX_SESSION_LENGTH=50
MEMORY_SESSION_TTL=3600

# LLM Settings
DASHSCOPE_API_KEY=your_api_key_here

# Qdrant Settings
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=agent_rag_knowledge
QDRANT_API_KEY=
```

### 4. 启动服务

#### 4.1 启动Qdrant

**使用Docker启动：**
```bash
docker run -p 6333:6333 qdrant/qdrant
```

**或使用本地安装：**
请参考 [Qdrant官方文档](https://qdrant.tech/documentation/quick-start/)

#### 4.2 启动Redis (可选)

**使用Docker启动：**
```bash
docker run -p 6379:6379 redis
```

#### 4.3 启动系统

```bash
# 在项目根目录运行
python start.py
```

### 5. 访问地址

- **前端界面**: http://localhost:3000
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **Qdrant控制台**: http://localhost:6333/dashboard

## API文档

### 核心API端点

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/api/rag/query` | POST | RAG查询 | `{"query": "...", "session_id": "..."}` | 带答案和来源的响应 |
| `/api/agent/invoke` | POST | Agent调用 | `{"query": "...", "session_id": "..."}` | 带意图和置信度的响应 |
| `/api/memory/operation` | POST | 记忆操作 | `{"session_id": "...", "operation": "get/clear/save"}` | 操作结果 |
| `/api/memory/sessions` | GET | 列出会话 | N/A | 会话ID列表 |
| `/api/agent/tools` | GET | 列出工具 | N/A | 工具列表 |
| `/health` | GET | 健康检查 | N/A | 服务状态 |

### 示例请求

**RAG查询：**
```json
POST /api/rag/query
{
  "query": "中央空调系统的COP值一般是多少？",
  "session_id": "session_123456"
}
```

**Agent调用：**
```json
POST /api/agent/invoke
{
  "query": "请帮我复核这份报价",
  "session_id": "session_123456"
}
```

## 前端使用指南

### 主要功能

1. **实时聊天**：与AI助手进行实时对话
2. **会话管理**：创建新会话、切换历史会话
3. **工具列表**：查看可用的AI工具
4. **记忆面板**：查看会话历史
5. **系统状态**：监控API状态和会话信息

### 操作流程

1. **启动系统**：运行 `python start.py`
2. **访问前端**：打开 http://localhost:3000
3. **开始对话**：在输入框中输入问题
4. **管理会话**：使用右上角的会话管理按钮
5. **查看结果**：AI助手会自动分析意图并调用相应工具

## 知识库管理

### 文档导入

使用 `langchain_rag/examples/quickstart.py` 中的 `example_05_document_processing()` 函数：

```python
from langchain_rag.document.processor import load_and_process_documents
from langchain_rag.vectorstore.qdrant import QdrantVectorStore, DashScopeEmbeddings

# 加载并处理文档
docs = load_and_process_documents(
    file_paths=[
        "data/hvac_design_guide.pdf",
        "data/chiller_manual.docx",
    ],
    chunk_size=512,
    chunk_overlap=100,
    document_type="技术文档",
)

# 存入向量库
embeddings = DashScopeEmbeddings(api_key="your_api_key")
vectorstore = QdrantVectorStore.from_documents(
    documents=docs,
    embeddings=embeddings,
    collection_name="hvac_knowledge",
)
```

### 支持的文档格式

- PDF (`.pdf`)
- Word (`.docx`, `.doc`)
- Excel (`.xlsx`, `.xls`)
- PowerPoint (`.pptx`, `.ppt`)
- CSV (`.csv`)
- 文本 (`.txt`, `.md`)

## 配置说明

### 核心配置文件

| 文件 | 说明 | 位置 |
|------|------|------|
| `backend/.env` | 环境变量配置 | `backend/.env` |
| `backend/config/settings.py` | 系统配置 | `backend/config/settings.py` |
| `langchain_rag/config/settings.py` | RAG配置 | `langchain_rag/config/settings.py` |

### 关键配置项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `MEMORY_TYPE` | 记忆存储类型 | `inmemory` |
| `MEMORY_MAX_SESSION_LENGTH` | 会话最大消息数 | `50` |
| `MEMORY_SESSION_TTL` | 会话过期时间(秒) | `3600` |
| `RAG_CHUNK_SIZE` | 文档分块大小 | `512` |
| `RAG_RETRIEVAL_TOP_K` | 检索结果数量 | `10` |
| `RAG_RERANK_TOP_K` | 重排序结果数量 | `5` |
| `AGENT_CONFIDENCE_THRESHOLD` | 置信度阈值 | `0.75` |

## 部署指南

### 开发环境

```bash
# 启动开发服务器
python start.py
```

### 生产环境

1. **使用Gunicorn**：
   ```bash
   cd backend
   gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
   ```

2. **使用Docker**：
   ```bash
   # 构建镜像
   docker build -t agentic-rag .
   
   # 运行容器
   docker run -p 8000:8000 -p 3000:3000 agentic-rag
   ```

3. **使用Nginx反向代理**：
   ```nginx
   server {
       listen 80;
       server_name example.com;
       
       location / {
           proxy_pass http://localhost:3000;
       }
       
       location /api/ {
           proxy_pass http://localhost:8000;
       }
   }
   ```

## 故障排查

### 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| API返回401错误 | DASHSCOPE_API_KEY错误 | 检查API Key是否正确 |
| 向量库连接失败 | Qdrant服务未启动 | 启动Qdrant服务 |
| 会话存储失败 | Redis服务未启动 | 启动Redis或使用内存存储 |
| 前端无法访问 | 端口被占用 | 检查端口8000和3000是否被占用 |
| 响应时间过长 | LLM调用超时 | 检查网络连接和API Key权限 |

### 日志查看

```bash
# 后端日志
python start.py 2>&1 | tee backend.log

# Qdrant日志
docker logs qdrant-container

# Redis日志
docker logs redis-container
```

## 性能优化

### 1. 向量库优化

- **增加Qdrant内存**：调整容器内存限制
- **使用SSD存储**：提高向量检索速度
- **优化索引**：调整HNSW参数

### 2. LLM优化

- **使用流式输出**：提高响应速度
- **缓存频繁查询**：减少重复计算
- **调整模型参数**：根据硬件配置调整temperature等参数

### 3. 系统优化

- **使用Redis**：提高会话管理效率
- **调整并发数**：根据服务器配置调整Gunicorn worker数量
- **使用CDN**：加速前端资源加载

## 安全最佳实践

1. **API Key管理**：
   - 使用环境变量存储API Key
   - 定期轮换API Key
   - 限制API Key权限

2. **CORS配置**：
   - 生产环境设置具体域名
   - 避免使用通配符

3. **数据安全**：
   - 加密存储敏感数据
   - 定期备份知识库
   - 限制访问权限

4. **网络安全**：
   - 使用HTTPS
   - 设置防火墙规则
   - 定期安全扫描

## 扩展功能

### 1. 多模型支持

```python
# 添加其他LLM支持
from langchain_rag.llm.openai import ChatOpenAI

llm = ChatOpenAI(
    model_name="gpt-4o",
    api_key="your_openai_key"
)
```

### 2. 自定义工具

```python
from langchain.tools import Tool

# 创建自定义工具
def custom_tool(input_text):
    """自定义工具功能"""
    return f"处理结果: {input_text}"

custom_tool = Tool(
    name="custom_tool",
    description="自定义工具描述",
    func=custom_tool
)

# 添加到Agent
tools.append(custom_tool)
```

### 3. 多模态支持

```python
# 添加图像识别功能
from langchain_rag.tools.image_tool import ImageAnalyzer

image_tool = ImageAnalyzer()
tools.append(image_tool)
```

## 项目结构

```
agent_rag/
├── langchain_rag/       # 核心RAG模块
│   ├── agent/           # Agent核心
│   ├── config/          # 配置管理
│   ├── document/        # 文档处理
│   ├── examples/        # 示例代码
│   ├── llm/             # LLM集成
│   ├── rag/             # RAG检索链
│   ├── tools/           # 工具集
│   └── vectorstore/     # 向量存储
├── backend/             # FastAPI后端
│   ├── api/             # API路由
│   ├── config/          # 配置管理
│   ├── services/        # 业务服务
│   ├── main.py          # 主应用
│   ├── requirements.txt # 依赖清单
│   └── .env             # 环境变量
├── frontend/            # 前端界面
│   └── index.html       # 单页应用
├── start.py             # 启动脚本
└── README.md            # 项目文档
```

## 许可证

MIT License

## 联系方式

- **项目维护者**：[Your Name]
- **邮箱**：[your.email@example.com]
- **GitHub**：[github.com/yourusername/agentic-rag]

---

**注意**：本项目仅供内部使用，所有数据操作严格遵循公司信息安全管理制度，确保proprietary知识不流出企业边界。
