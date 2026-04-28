"""
报价审核模块 (Quote Audit)

5层Pipeline系统：
- Layer 1: 数据清洗与标准化 (Excel解析 + 空值/重复检测 + 备注解析)
- Layer 2: GB 50500合规检查 (单位一致性 + 特征完整性 + 甲供校验)
- Layer 3: 算术校验引擎 (横向量价校验 + 纵向汇总校验 + 费用层级校验)
- Layer 4: 造价指标分析 (单方造价 + 占比分析 + Qdrant历史对标)
- Layer 5: 风险预警与报告生成 (问题分级 + 状态判定 + Markdown报告)

使用示例：
    from langchain_rag.quote_audit import QuoteAuditPipeline

    pipeline = QuoteAuditPipeline()
    report = pipeline.run(
        excel_path="合同清单.xlsx",
        project_name="珠海某PCB厂高效机房项目"
    )
"""

from .pipeline import QuoteAuditPipeline
from .models import (
    BillItem,
    BillSection,
    BillSummary,
    ComplianceFinding,
    ArithmeticError,
    CostIndexResult,
    AuditIssue,
    QuoteAuditReport,
    PipelineContext,
)

__all__ = [
    "QuoteAuditPipeline",
    "BillItem",
    "BillSection",
    "BillSummary",
    "ComplianceFinding",
    "ArithmeticError",
    "CostIndexResult",
    "AuditIssue",
    "QuoteAuditReport",
    "PipelineContext",
]

__version__ = "1.0.0"
