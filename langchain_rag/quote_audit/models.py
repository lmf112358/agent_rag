"""
报价审核数据模型 (Pydantic Models)

定义5层Pipeline中使用的所有数据结构
"""

from typing import Optional, List, Dict, Any, Literal, Union
from decimal import Decimal, ROUND_HALF_UP
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


# ==================== 类型别名 ====================

Severity = Literal["fatal", "major", "warning", "info"]
Phase = Literal["一期", "二期", "未知"]
OwnerSupplyStatus = Literal["甲供", "非甲供", "待确认"]


# ==================== Layer 0: Excel解析输出 ====================

class ExcelSheetResult(BaseModel):
    """单个Sheet解析结果"""
    sheet_name: str
    phase: Phase = "未知"
    raw_headers: List[str] = Field(default_factory=list)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    section_breaks: List[int] = Field(default_factory=list)


# ==================== Layer 1: 标准化条目 ====================

class BillItem(BaseModel):
    """分部分项工程量清单条目"""
    # 基础信息
    sequence: str = ""
    section: str = ""
    item_name: str = ""
    item_features: str = ""

    # 品牌型号
    brand: Optional[str] = None
    model_spec: Optional[str] = None

    # 计量
    unit: str = ""
    quantity: Decimal = Decimal("0")

    # 单价（双列体系）
    material_unit_price: Optional[Decimal] = None
    labor_unit_price: Optional[Decimal] = None

    # 合价（双列体系）
    material_total: Optional[Decimal] = None
    labor_total: Optional[Decimal] = None

    # 元数据
    remarks: Optional[str] = None
    phase: Phase = "未知"

    # 派生字段
    item_total: Optional[Decimal] = None
    is_owner_supply: bool = False
    owner_supply_status: OwnerSupplyStatus = "非甲供"
    tech_tags: List[str] = Field(default_factory=list)

    # 行号（用于报告定位）
    row_index: int = 0

    @field_validator(
        "quantity", "material_unit_price", "labor_unit_price",
        "material_total", "labor_total", "item_total",
        mode="before",
    )
    @classmethod
    def coerce_to_decimal(cls, v):
        if v is None or v == "" or v == "-" or v == "—":
            return None
        try:
            return Decimal(str(v))
        except Exception:
            return None


class BillSection(BaseModel):
    """分部工程"""
    section_id: str = ""
    section_name: str = ""
    items: List[BillItem] = Field(default_factory=list)
    subtotal_material: Decimal = Decimal("0")
    subtotal_labor: Decimal = Decimal("0")
    phase: Phase = "未知"

    # 校验字段
    calculated_material: Optional[Decimal] = None
    calculated_labor: Optional[Decimal] = None
    subtotal_errors: List[Dict[str, Any]] = Field(default_factory=list)


class BillSummary(BaseModel):
    """费用汇总"""
    phase: Phase = "一期"
    subtotal_material: Decimal = Decimal("0")
    subtotal_labor: Decimal = Decimal("0")
    direct_cost: Decimal = Decimal("0")
    measures_cost: Decimal = Decimal("0")
    tax: Decimal = Decimal("0")
    grand_total: Decimal = Decimal("0")

    # 校验字段
    summary_errors: List[Dict[str, Any]] = Field(default_factory=list)


# ==================== Layer 2: 合规发现 ====================

class ComplianceFinding(BaseModel):
    """GB 50500合规发现"""
    item_sequence: str = ""
    item_name: str = ""
    finding_type: str = ""       # unit_inconsistency / feature_incomplete / owner_supply_pricing
    severity: Severity = "warning"
    message: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)


# ==================== Layer 3: 算术错误 ====================

class ArithmeticError(BaseModel):
    """算术校验错误"""
    item_sequence: str = ""
    item_name: str = ""
    error_type: str = ""         # material_mismatch / labor_mismatch / subtotal_mismatch / fee_mismatch
    expected: Optional[Decimal] = None
    actual: Optional[Decimal] = None
    difference: Optional[Decimal] = None
    severity: Severity = "warning"


# ==================== Layer 4: 造价指标 ====================

class CostIndexResult(BaseModel):
    """造价指标分析结果"""
    phase: Phase = "一期"
    unit_cost_per_rt: Optional[Decimal] = None
    unit_cost_per_sqm: Optional[Decimal] = None
    material_ratio: Optional[Decimal] = None
    labor_ratio: Optional[Decimal] = None
    measures_ratio: Optional[Decimal] = None
    tax_ratio: Optional[Decimal] = None
    alerts: List[Dict[str, Any]] = Field(default_factory=list)
    historical_comparison: Dict[str, Any] = Field(default_factory=dict)


# ==================== Layer 5: 审核问题与报告 ====================

class AuditIssue(BaseModel):
    """统一审核问题"""
    issue_id: str = ""
    severity: Severity = "warning"
    category: str = ""           # data_quality / compliance / arithmetic / cost_anomaly
    location: str = ""
    message: str = ""
    expected: Optional[str] = None
    actual: Optional[str] = None
    suggestion: str = ""


class QuoteAuditReport(BaseModel):
    """最终审核报告"""
    report_id: str = ""
    project_name: str = ""
    audit_time: datetime = Field(default_factory=datetime.now)
    overall_status: str = ""     # pass / conditional_pass / fail
    total_items: int = 0
    fatal_count: int = 0
    major_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    pass_rate: Decimal = Decimal("0")

    # 结构化数据
    sections: List[BillSection] = Field(default_factory=list)
    summaries: List[BillSummary] = Field(default_factory=list)
    compliance_findings: List[ComplianceFinding] = Field(default_factory=list)
    arithmetic_errors: List[ArithmeticError] = Field(default_factory=list)
    cost_indices: List[CostIndexResult] = Field(default_factory=list)
    issues: List[AuditIssue] = Field(default_factory=list)
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)

    # 项目元数据
    total_rt: Optional[Decimal] = None
    building_area: Optional[Decimal] = None

    # Markdown报告
    markdown: str = ""


# ==================== Pipeline上下文 ====================

class PipelineContext(BaseModel):
    """Pipeline阶段间传递的上下文"""
    project_name: str = ""
    excel_path: str = ""
    sheets: List[ExcelSheetResult] = Field(default_factory=list)
    items: List[BillItem] = Field(default_factory=list)
    sections: List[BillSection] = Field(default_factory=list)
    summaries: List[BillSummary] = Field(default_factory=list)
    compliance_findings: List[ComplianceFinding] = Field(default_factory=list)
    arithmetic_errors: List[ArithmeticError] = Field(default_factory=list)
    cost_indices: List[CostIndexResult] = Field(default_factory=list)
    report: Optional[QuoteAuditReport] = None
    stage_times: Dict[str, float] = Field(default_factory=dict)

    # 项目元数据
    total_rt: Optional[Decimal] = None
    building_area: Optional[Decimal] = None

    # 费率覆盖
    fee_rates: Dict[str, Any] = Field(default_factory=dict)
