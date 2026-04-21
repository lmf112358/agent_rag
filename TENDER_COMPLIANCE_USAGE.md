# 标书审核Agent 使用指南

## 快速开始

### 1. 配置环境变量

编辑 `langchain_rag/.env` 文件，填入实际的API密钥：

```bash
# MinerU 云端接口配置
MINERU_API_BASE=https://your-mineru-api.com  # 替换为实际的MinerU云端API地址
MINERU_API_KEY=your_mineru_api_key_here      # 替换为实际的API密钥

# DashScope API配置（用于LLM调用）
DASHSCOPE_API_KEY=your_dashscope_key_here

# Qdrant 向量库配置（可选，用于KB验证）
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

### 2. 运行演示

```bash
# 方式1：运行演示脚本（无需PDF文件，查看Pipeline流程）
python examples/tender_compliance_demo.py

# 方式2：使用真实PDF文件运行
python examples/tender_compliance_demo.py --with-files
```

### 3. 编程方式使用

```python
from langchain_rag.tender_compliance import TenderCompliancePipeline

# 初始化Pipeline（自动从.env读取配置）
pipeline = TenderCompliancePipeline()

# 运行完整审核流程
report = pipeline.run(
    tender_pdf="path/to/tender.pdf",      # 招标书PDF路径
    bid_pdf="path/to/bid.pdf",            # 投标书PDF路径
    project_name="珠海某PCB厂高效机房项目",  # 项目名称
    project_type="高效机房",               # 项目类型
    company_name="投标公司名称"             # 投标公司名称
)

# 查看审核结果
print(f"总得分: {report.scoring_card.total_score}")
print(f"废标风险: {'有' if report.scoring_card.disqualification_risk else '无'}")
print(f"报告ID: {report.report_id}")
```

## 5阶段Pipeline说明

| 阶段 | 名称 | 功能 | 输出 |
|------|------|------|------|
| Stage 1 | 文档解析层 | 调用MinerU解析PDF为Markdown | 解析后的文档对象 |
| Stage 2 | 条款对齐层 | 识别章节、提取条款、对齐响应 | 结构化Checklist和响应JSON |
| Stage 3 | 核对引擎层 | Hard/Soft/KB三层核对 | 核对结果列表 |
| Stage 4 | 评分汇总层 | 多维度评分、风险标记 | 评分卡和汇总统计 |
| Stage 5 | 人工复核层 | 自动分流、报告生成 | 审核报告和决策建议 |

## 配置文件说明

### 章节识别规则 (`config.py`)

```python
TENDER_SECTION_PATTERNS = {
    "技术要求": {"keywords": ["技术", "参数", "规格", "性能"]},
    "商务条款": {"keywords": ["商务", "价格", "付款", "交货"]},
    "资质要求": {"keywords": ["资质", "证书", "业绩", "经验"]},
}
```

### 评分维度配置 (`config.py`)

```python
SCORING_DIMENSIONS = {
    "技术响应性": {"weight": 0.4, "max_score": 40},
    "技术先进性": {"weight": 0.2, "max_score": 20},
    "实施能力": {"weight": 0.2, "max_score": 20},
    "服务保障": {"weight": 0.2, "max_score": 20},
}
```

## 常见问题

### Q: MinerU 云端API返回401错误
**A:** 检查 `.env` 文件中的 `MINERU_API_KEY` 是否正确设置

### Q: DashScope API调用失败
**A:** 检查 `.env` 文件中的 `DASHSCOPE_API_KEY` 是否设置正确

### Q: 如何只运行单个Stage进行调试
**A:** 
```python
# 只运行Stage 1（文档解析）
pipeline = TenderCompliancePipeline()
tender_doc, bid_doc = pipeline.run_stage_only(
    stage=1,
    tender_pdf='tender.pdf',
    bid_pdf='bid.pdf',
    tender_id='T001',
    bid_id='B001',
    project_name='测试项目',
    project_type='高效机房',
    company_name='测试公司'
)
```

## 更多帮助

如需更多帮助，请查看:
- 演示脚本: `examples/tender_compliance_demo.py`
- 快速开始: `examples/tender_quickstart.py`
- 数据模型: `langchain_rag/tender_compliance/models.py`
- 配置文件: `langchain_rag/tender_compliance/config.py`
