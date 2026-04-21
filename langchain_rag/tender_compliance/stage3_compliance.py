"""
Stage 3: 核对引擎层 (Compliance Engine)

负责：
1. Hard Check: 数值硬规则核对（Python计算）
2. Soft Check: 语义评估核对（LLM辅助）
3. KB Verify: 知识库校验（Qdrant查询）

输出每条条款的三层核对结果
"""

import logging
from typing import List, Dict, Any, Optional, Callable, Union
from dataclasses import dataclass

from .models import (
    TenderChecklist,
    BidResponse,
    ComplianceResult,
    ComplianceCheck,
    HardCheckResult,
    SoftCheckResult,
    KBVerifyResult,
    TenderItem,
    MetricSpec,
    EquipmentRow,
    ComplianceStatus,
    DeviationType,
    RiskLevel,
)
from .config import COMPLIANCE_ENGINE_CONFIG

logger = logging.getLogger(__name__)


class HardCheckEngine:
    """
    Hard Check: 数值硬规则引擎

    纯Python计算，无LLM参与，确保可审计性
    """

    OPERATORS: Dict[str, Callable] = {
        ">=": lambda x, y: x >= y,
        "<=": lambda x, y: x <= y,
        ">": lambda x, y: x > y,
        "<": lambda x, y: x < y,
        "==": lambda x, y: x == y,
        "in_range": lambda x, y: y[0] <= x <= y[1] if isinstance(y, (list, tuple)) and len(y) == 2 else False,
        "in_list": lambda x, y: x in y if isinstance(y, (list, tuple)) else False,
    }

    def check(self, tender_item: TenderItem, bid_response: Dict[str, Any]) -> HardCheckResult:
        """
        执行Hard Check核对

        Args:
            tender_item: 招标条款项
            bid_response: 投标响应数据

        Returns:
            HardCheckResult: 硬核对结果
        """
        # 如果没有量化指标，无法进行Hard Check
        if not tender_item.quantifiable or not tender_item.metric:
            return HardCheckResult(
                status="未响应",
                deviation_type="未响应",
                bid_value=None,
                target_value=None,
                risk_level="高",
                action="无法进行数值核对，需人工审核",
            )

        metric = tender_item.metric

        # 从投标响应中提取对应值
        bid_value = self._extract_bid_value(
            tender_item, bid_response, metric.parameter
        )

        if bid_value is None:
            return HardCheckResult(
                status="未响应",
                deviation_type="未响应",
                bid_value=None,
                target_value=metric.target_value,
                operator=metric.operator,
                risk_level="高" if tender_item.penalty_type == "废标" else "中",
                penalty_type=tender_item.penalty_type,
                action="强制人工审核" if tender_item.penalty_type == "废标" else "需处理",
            )

        # 执行比较
        try:
            operator_func = self.OPERATORS.get(metric.operator)
            if not operator_func:
                logger.warning(f"未知的操作符: {metric.operator}")
                is_compliant = False
            else:
                is_compliant = operator_func(bid_value, metric.target_value)

        except Exception as e:
            logger.error(f"数值比较失败: {e}")
            is_compliant = False

        # 计算偏离幅度
        margin = None
        margin_percent = None
        if isinstance(bid_value, (int, float)) and isinstance(metric.target_value, (int, float)):
            margin = bid_value - metric.target_value
            if metric.target_value != 0:
                margin_percent = (margin / metric.target_value) * 100

        # 判定偏离类型
        if is_compliant:
            if margin is not None and margin > 0:
                deviation_type = "正偏离"  # 优于要求
            else:
                deviation_type = "符合"
        else:
            deviation_type = "负偏离" if margin is not None and margin < 0 else "不符合"

        # 风险等级
        if tender_item.penalty_type == "废标" and not is_compliant:
            risk_level = "极高"
        elif not is_compliant:
            risk_level = "高"
        elif deviation_type == "正偏离":
            risk_level = "低"
        else:
            risk_level = "无"

        return HardCheckResult(
            status="符合" if is_compliant else "不符合",
            deviation_type=deviation_type,
            bid_value=bid_value,
            target_value=metric.target_value,
            operator=metric.operator,
            margin=margin,
            margin_percent=margin_percent,
            unit=metric.unit,
            risk_level=risk_level,
            penalty_type=tender_item.penalty_type,
            action="通过" if is_compliant else "需处理",
        )

    def _extract_bid_value(
        self,
        tender_item: TenderItem,
        bid_response: Dict[str, Any],
        parameter: str,
    ) -> Optional[Any]:
        """
        从投标响应中提取指定参数的值

        简化实现，实际需要更复杂的映射逻辑
        """
        # 从设备参数表中查找
        equipment_tables = bid_response.get("equipment_tables", [])

        for table in equipment_tables:
            rows = table.get("rows", [])
            for row in rows:
                params = row.get("parameters", {})

                # 参数名映射
                param_mapping = {
                    "COP": ["COP", "cop"],
                    "IPLV": ["IPLV", "iplv"],
                    "制冷量": ["制冷量_kW", "制冷量", "制冷量(kW)"],
                    "输入功率": ["输入功率_kW", "输入功率", "功率"],
                }

                possible_keys = param_mapping.get(parameter, [parameter])
                for key in possible_keys:
                    if key in params:
                        return params[key]

        return None


class SoftCheckEngine:
    """
    Soft Check: 语义评估引擎

    使用LLM进行语义评估
    """

    def __init__(
        self,
        llm_model: str = "qwen-max",
        confidence_threshold: float = 0.7,
    ):
        self.llm_model = llm_model
        self.confidence_threshold = confidence_threshold

    def check(
        self,
        tender_item: TenderItem,
        bid_response: Dict[str, Any],
    ) -> SoftCheckResult:
        """
        执行Soft Check语义评估

        简化实现，实际应调用LLM
        """
        # TODO: 实现LLM调用
        # 这里返回一个占位结果

        return SoftCheckResult(
            is_responded="待评估",
            response_quality="待评估",
            suggested_score=0,
            max_score=tender_item.score_weight,
            confidence=0.0,
            reasoning="Soft Check尚未实现",
            evidence="",
            needs_manual_review=True,
        )


class KBVerifyEngine:
    """
    KB Verify: 知识库校验引擎

    使用Qdrant查询验证厂家参数
    """

    def __init__(
        self,
        qdrant_host: Optional[str] = None,
        collection: str = "hvac_equipment",
        deviation_threshold: float = 10.0,
    ):
        self.qdrant_host = qdrant_host
        self.collection = collection
        self.deviation_threshold = deviation_threshold

    def verify(
        self,
        tender_item: TenderItem,
        bid_response: Dict[str, Any],
    ) -> KBVerifyResult:
        """
        执行KB知识库校验

        简化实现，实际应查询Qdrant
        """
        # TODO: 实现Qdrant查询
        # 这里返回一个占位结果

        return KBVerifyResult(
            kb_matched=False,
            model_found=False,
            parameter_alerts=[],
            kb_value=None,
            bid_value=None,
            deviation_percent=None,
        )


class Stage3Compliance:
    """
    Stage 3: 核对引擎层主类

    整合Hard Check、Soft Check、KB Verify三层核对
    """

    def __init__(
        self,
        llm_model: str = "qwen-max",
        qdrant_host: Optional[str] = None,
        enable_kb_verify: bool = True,
    ):
        self.hard_engine = HardCheckEngine()
        self.soft_engine = SoftCheckEngine(llm_model=llm_model)

        if enable_kb_verify and qdrant_host:
            self.kb_engine = KBVerifyEngine(qdrant_host=qdrant_host)
        else:
            self.kb_engine = None

    def check(
        self,
        checklist: TenderChecklist,
        bid_response: BidResponse,
    ) -> ComplianceResult:
        """
        执行三层核对

        Args:
            checklist: 招标书Checklist
            bid_response: 投标书响应

        Returns:
            ComplianceResult: 核对结果
        """
        logger.info(f"[Stage 3] 执行三层核对: {len(checklist.items)}条条款")

        checks = []
        hard_count = 0
        soft_count = 0
        kb_count = 0

        for item in checklist.items:
            check = ComplianceCheck(
                item_id=item.item_id,
                check_type=self._determine_check_type(item),
            )

            # Hard Check: 量化指标
            if item.quantifiable and item.metric:
                hard_result = self.hard_engine.check(item, bid_response.dict())
                check.hard_result = hard_result
                check.final_status = hard_result.status
                check.final_risk_level = hard_result.risk_level
                hard_count += 1

            # Soft Check: 定性评估
            elif item.type == "评分项":
                soft_result = self.soft_engine.check(item, bid_response.dict())
                check.soft_result = soft_result
                check.final_status = "待评估" if check.final_status is None else check.final_status
                soft_count += 1

            # KB Verify: 知识库校验（可选）
            if self.kb_engine and item.quantifiable:
                kb_result = self.kb_engine.verify(item, bid_response.dict())
                check.kb_result = kb_result
                kb_count += 1

            checks.append(check)

        logger.info(f"  Hard Check: {hard_count}项")
        logger.info(f"  Soft Check: {soft_count}项")
        logger.info(f"  KB Verify: {kb_count}项")

        # 生成汇总统计
        summary = self._generate_summary(checks)

        return ComplianceResult(
            tender_id=checklist.tender_id,
            bid_id=bid_response.bid_id,
            checks=checks,
            summary=summary,
        )

    def _determine_check_type(self, item: TenderItem) -> str:
        """确定核对类型"""
        if item.quantifiable:
            return "Hard"
        elif item.type == "评分项":
            return "Soft"
        else:
            return "Hard"  # 默认

    def _generate_summary(self, checks: List[ComplianceCheck]) -> Dict[str, Any]:
        """生成核对结果汇总"""
        total = len(checks)

        # Hard Check统计
        hard_checks = [c for c in checks if c.hard_result]
        hard_passed = sum(1 for c in hard_checks if c.hard_result.status == "符合")
        hard_failed = sum(1 for c in hard_checks if c.hard_result.status == "不符合")

        # 风险等级统计
        high_risk = sum(1 for c in checks if c.final_risk_level in ["高", "极高"])
        medium_risk = sum(1 for c in checks if c.final_risk_level == "中")

        return {
            "total_items": total,
            "hard_check": {
                "total": len(hard_checks),
                "passed": hard_passed,
                "failed": hard_failed,
                "not_checked": len(hard_checks) - hard_passed - hard_failed,
            },
            "risk_summary": {
                "high_risk": high_risk,
                "medium_risk": medium_risk,
                "low_risk": total - high_risk - medium_risk,
            },
            "compliance_rate": hard_passed / len(hard_checks) * 100 if hard_checks else 0,
        }
