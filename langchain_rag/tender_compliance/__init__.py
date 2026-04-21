"""
标书审核合规性检查模块 (Tender Compliance Checker)

5阶段Pipeline系统：
- Stage 1: 文档解析层 (复用MinerU + QualityChecker)
- Stage 2: 条款对齐层 (章节识别 + 条款提取)
- Stage 3: 核对引擎层 (Hard/Soft/KB三层核对)
- Stage 4: 评分汇总层 (多维度评分 + 风险标记)
- Stage 5: 人工复核层 (自动分流 + 审核报告)

使用示例：
    from langchain_rag.tender_compliance import TenderCompliancePipeline

    pipeline = TenderCompliancePipeline()
    result = pipeline.run(
        tender_pdf="招标书.pdf",
        bid_pdf="投标书.pdf"
    )
"""

from .pipeline import TenderCompliancePipeline
from .models import (
    TenderChecklist,
    BidResponse,
    ComplianceResult,
    ScoringCard,
    ReviewReport,
)

__all__ = [
    "TenderCompliancePipeline",
    "TenderChecklist",
    "BidResponse",
    "ComplianceResult",
    "ScoringCard",
    "ReviewReport",
]

__version__ = "1.0.0"
