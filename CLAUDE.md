# CLAUDE.md

本文件用于约束 Claude 在本仓库内的协作方式，目标是：小步快改、可验证、与现有实现保持一致。

## 沟通与输出

- 默认使用中文，回复简洁，先给结果再给细节。
- 引用代码位置使用 `path:line` 格式。
- 不做无关重构，不增加与需求无关的“优化”。

## 工具与修改原则

- 文件读取优先用 `Read`，内容搜索用 `Grep`，文件搜索用 `Glob`。
- 修改现有文件前先完整读取目标文件，再做精确修改。
- 优先最小改动，修复根因，不做表面绕过。
- 非必要不新建文件；若必须新建，内容应直接可运行或可验证。

## 项目结构速览

- 核心 RAG 模块：`langchain_rag/`
- 后端 API：`backend/`
- 启动脚本：`start.py`、`start.sh`、`start.bat`
- 关键实现：
  - Qwen LLM：`langchain_rag/llm/qwen.py`
  - Qdrant 向量库：`langchain_rag/vectorstore/qdrant.py`
  - 检索链：`langchain_rag/rag/retrieval.py`
  - 后端服务：`backend/services/`

## 环境与配置

- Python 环境建议：`conda activate agent_rag`
- 配置文件优先使用：`langchain_rag/.env`
- 最关键变量：
  - `DASHSCOPE_API_KEY`
  - `QDRANT_HOST` / `QDRANT_PORT` / `QDRANT_API_KEY`
  - `LLM_MODEL_NAME`、`EMBEDDING_MODEL_NAME`
- 使用 Qdrant Cloud 时，`QDRANT_HOST` 可直接填完整 URL（含 `https://`）。

### MinerU 配置

- `MINERU_API_BASE`: MinerU 服务地址，官方云端 API 为 `https://mineru.net`
- `MINERU_API_KEY`: MinerU API 密钥（云端 API 必需）
- `MINERU_ENABLED`: 是否启用 MinerU（`true`/`false`）
- `MINERU_TIMEOUT`: 解析超时时间（秒）
- `MINERU_OUTPUT_FORMAT`: 输出格式（`markdown`/`json`）
- `MINERU_ENABLE_OCR`: 是否启用 OCR（`true`/`false`）
- `MINERU_ENABLE_FORMULA`: 是否启用公式识别（`true`/`false`）
- `MINERU_ENABLE_TABLE`: 是否启用表格识别（`true`/`false`）

**注意**: `.env` 文件只增不减，配置变更需记录于此。

## 启动方式

- 一键启动前后端：`python start.py`
- 仅启动后端（开发）：`cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
- Linux/macOS：`bash start.sh`（生产模式：`bash start.sh prod`）
- Windows：`start.bat`

## 测试与验证

- 优先运行与改动直接相关的测试，再考虑全量测试。
- 常用命令：
  - `pytest -q`
  - `pytest langchain_rag/tests/test_qwen.py -q`
  - `pytest langchain_rag/tests/test_vectorstore.py -q`
- 完成前至少做一次最小可复现验证（导入、接口或单测其一）。

## 本项目已知易错点

- Qdrant Distance 枚举按成员名处理：`COSINE`/`EUCLID`/`DOT`/`MANHATTAN`。
- Qwen 调用需确保 `Generation.call(...)` 传入 `api_key`。
- `AIMessage` 仅在有工具调用时传 `tool_calls` 字段，避免 `None` 校验错误。
- 处理 DashScope 返回结构时，优先使用安全访问，避免 `KeyError`。

## 提交约定

- 未明确要求时，不主动执行 `git commit`、`git push`。
- 任何潜在破坏性操作（删除、重置、覆盖）先确认再执行。
