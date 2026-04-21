"""
标书审核数据模型 (Pydantic Models)

定义5阶段Pipeline中使用的所有数据结构
"""

from typing import Optional, List, Dict, Any, Literal, Union
from dataclasses import dataclass, field
from datetime import datetime
from pydantic import BaseModel, Field


# ==================== 基础类型 ====================

QualityTag = Literal["CLEAN", "SCANNED", "CORRUPTED", "ENCRYPTED", "GARBAGE_ENCODING", "UNSUPPORTED_FORMAT"]
ComplianceStatus = Literal["符合", "不符合", "部分符合", "未响应"]
DeviationType = Literal["符合", "正偏离", "负偏离", "未响应"]
RiskLevel = Literal["无", "低", "中", "高", "极高"]
CheckType = Literal["Hard", "Soft", "KB"]
ItemType = Literal["硬性指标", "评分项", "资质要求", "商务条款", "其他"]


# ==================== Stage 1: 文档解析层 ====================

class DocumentParseResult(BaseModel):
    """文档解析结果"""
    success: bool
    markdown: Optional[str] = None
    quality_report: Optional[Dict[str, Any]] = None
    page_count: int = 0
    error: Optional[str] = None
    parse_time_seconds: float = 0.0


class TenderDocument(BaseModel):
    """招标书文档"""
    tender_id: str
    project_name: str
    project_type: str = "高效机房"
    pdf_path: str
    parse_result: Optional[DocumentParseResult] = None
    markdown: Optional[str] = None
    parse_version: str = "1.0"


class BidDocument(BaseModel):
    """投标书文档"""
    bid_id: str
    tender_id: str
    company_name: str
    pdf_path: str
    parse_result: Optional[DocumentParseResult] = None
    markdown: Optional[str] = None


# ==================== Stage 2: 条款对齐层 ====================

class MetricSpec(BaseModel):
    """量化指标规格"""
    parameter: str
    operator: str = ">="  # >=, <=, >, <, ==, in_range, in_list
    target_value: Union[float, int, str, List[float]]
    unit: Optional[str] = None
    test_condition: Optional[str] = None


class TenderItem(BaseModel):
    """招标条款项"""
    item_id: str
    sequence: str
    section_id: str
    type: ItemType
    content: str
    quantifiable: bool = False
    metric: Optional[MetricSpec] = None
    keywords: List[str] = Field(default_factory=list)
    penalty_type: str = ""  # 废标, 扣分, 无
    score_weight: float = 0.0
    score_rule: Optional[str] = None
    page_ref: int = 0
    confidence: float = 0.0
    needs_manual_check: bool = False


class TenderChecklist(BaseModel):
    """招标书结构化Checklist"""
    tender_id: str
    project_name: str
    project_type: str
    parse_version: str = "1.0"
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    items: List[TenderItem] = Field(default_factory=list)
    statistics: Dict[str, int] = Field(default_factory=dict)


class EquipmentRow(BaseModel):
    """设备参数表行"""
    row_id: str
    sequence: int
    equipment_name: str
    model_spec: str
    brand: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    remarks: Optional[str] = None


class EquipmentTable(BaseModel):
    """设备参数表"""
    table_id: str
    table_title: str
    page_ref: int
    headers: List[str] = Field(default_factory=list)
    rows: List[EquipmentRow] = Field(default_factory=list)


class DeviationItem(BaseModel):
    """偏离表项"""
    tender_item_id: str
    tender_requirement: str
    bid_response: str
    deviation_type: DeviationType
    deviation_note: Optional[str] = None


class TechnicalSection(BaseModel):
    """技术方案章节"""
    section_title: str
    content: str
    page_ref: int
    keywords: List[str] = Field(default_factory=list)


class QualificationDoc(BaseModel):
    """资质文件"""
    doc_type: str
    provided: bool
    page_ref: Optional[int] = None
    count: Optional[int] = None


class BidResponse(BaseModel):
    """投标书响应提取"""
    bid_id: str
    tender_id: str
    project_name: str
    equipment_tables: List[EquipmentTable] = Field(default_factory=list)
    deviation_table: Dict[str, Any] = Field(default_factory=dict)
    technical_proposal: Dict[str, Any] = Field(default_factory=dict)
    qualification_docs: List[QualificationDoc] = Field(default_factory=list)


# ==================== Stage 3: 核对引擎层 ====================

class HardCheckResult(BaseModel):
    """Hard Check数值核对结果"""
    status: ComplianceStatus
    deviation_type: DeviationType
    bid_value: Optional[Any] = None
    target_value: Optional[Any] = None
    operator: Optional[str] = None
    margin: Optional[float] = None
    margin_percent: Optional[float] = None
    unit: Optional[str] = None
    risk_level: RiskLevel = "无"
    penalty_type: Optional[str] = None
    action: str = ""  # 通过/需处理/强制人工审核


class SoftCheckResult(BaseModel):
    """Soft Check语义评估结果"""
    is_responded: str  # 是/部分/否
    response_quality: str  # 优/良/一般/差
    suggested_score: float
    max_score: float
    confidence: float
    reasoning: str
    evidence: str
    needs_manual_review: bool


class KBVerifyResult(BaseModel):
    """知识库校验结果"""
    kb_matched: bool
    model_found: bool
    parameter_alerts: List[Dict[str, Any]] = Field(default_factory=list)
    kb_value: Optional[Any] = None
    bid_value: Optional[Any] = None
    deviation_percent: Optional[float] = None


class ComplianceCheck(BaseModel):
    """单项合规核对"""
    item_id: str
    check_type: CheckType
    hard_result: Optional[HardCheckResult] = None
    soft_result: Optional[SoftCheckResult] = None
    kb_result: Optional[KBVerifyResult] = None
    final_status: Optional[ComplianceStatus] = None
    final_risk_level: Optional[RiskLevel] = None


class ComplianceResult(BaseModel):
    """核对引擎层输出"""
    tender_id: str
    bid_id: str
    checks: List[ComplianceCheck] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


# ==================== Stage 4 & 5: 评分与复核 ====================

class DimensionScore(BaseModel):
    """评分维度得分"""
    dimension: str
    weight: float
    max_score: float
    actual_score: float
    item_count: int
    passed_count: int
    failed_count: int
    risk_items: List[str] = Field(default_factory=list)


class ScoringCard(BaseModel):
    """评分汇总卡"""
    tender_id: str
    bid_id: str
    total_score: float
    max_total_score: float
    score_percent: float
    dimensions: List[DimensionScore] = Field(default_factory=list)
    risk_summary: Dict[str, Any] = Field(default_factory=dict)
    disqualification_risk: bool = False
    disqualification_reasons: List[str] = Field(default_factory=list)


class ReviewDecision(BaseModel):
    """复核决策"""
    item_id: str
    auto_decision: str  # 自动通过/需人工确认/强制人工审核
    confidence: float
    final_decision: Optional[str] = None  # 人工最终决策
    reviewer: Optional[str] = None
    review_time: Optional[datetime] = None
    review_comment: Optional[str] = None


class ReviewReport(BaseModel):
    """审核报告"""
    report_id: str
    tender_id: str
    bid_id: str
    project_name: str
    generated_at: datetime = Field(default_factory=datetime.now)
    checklist: Optional[TenderChecklist] = None
    bid_response: Optional[BidResponse] = None
    compliance_result: Optional[ComplianceResult] = None
    scoring_card: Optional[ScoringCard] = None
    review_decisions: List[ReviewDecision] = Field(default_factory=list)
    final_report: Dict[str, Any] = Field(default_factory=dict)

