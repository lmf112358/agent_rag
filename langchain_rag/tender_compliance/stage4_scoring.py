"""
Stage 4: 评分汇总层 (Scoring Engine)

负责：
1. 按维度权重计算得分
2. 风险等级标记
3. 废标风险检测
4. 生成评分卡
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

from .models import (
    TenderChecklist,
    ComplianceResult,
    ScoringCard,
    DimensionScore,
    ComplianceCheck,
    ComplianceStatus,
)
from .config import SCORING_DIMENSIONS

logger = logging.getLogger(__name__)


class Stage4Scoring:
    """
    Stage 4: 评分汇总引擎

    根据核对结果计算最终评分
    """

    def __init__(self):
        self.dimensions_config = SCORING_DIMENSIONS

    def score(
        self,
        checklist: TenderChecklist,
        compliance_result: ComplianceResult,
    ) -> ScoringCard:
        """
        执行评分汇总

        Args:
            checklist: 招标书Checklist
            compliance_result: 核对结果

        Returns:
            ScoringCard: 评分卡
        """
        import time
        start_time = time.time()

        logger.info(f"[Stage 4] 开始评分汇总")
        logger.info(f"  核对项数: {len(compliance_result.checks)}条")
        logger.info(f"  评分维度: {len(self.dimensions_config)}个")

        dimensions = []
        total_score = 0.0
        max_total_score = 0.0

        # 按维度评分
        logger.info(f"  计算各维度得分...")
        for dim_name, dim_config in self.dimensions_config.items():
            logger.debug(f"    维度: {dim_name} (权重:{dim_config.get('weight', 0):.0%})")
            dim_score = self._score_dimension(
                dim_name=dim_name,
                dim_config=dim_config,
                checklist=checklist,
                compliance_result=compliance_result,
            )
            dimensions.append(dim_score)

            logger.info(f"      {dim_name}: {dim_score.actual_score:.2f}/{dim_score.max_score:.2f} "
                       f"({dim_score.passed_count}/{dim_score.item_count}通过)")

            total_score += dim_score.actual_score
            max_total_score += dim_score.max_score

        # 废标风险检测
        logger.info(f"  检测废标风险...")
        disqualification_risk, disqualification_reasons = self._check_disqualification(
            compliance_result
        )

        if disqualification_risk:
            logger.warning(f"    ⚠ 检测到废标风险:")
            for reason in disqualification_reasons:
                logger.warning(f"      - {reason}")
        else:
            logger.info(f"    ✓ 无废标风险")

        # 风险汇总
        risk_summary = self._summarize_risks(compliance_result)

        score_percent = (total_score / max_total_score * 100) if max_total_score > 0 else 0

        logger.info(f"")
        logger.info(f"  {'='*50}")
        logger.info(f"  总得分: {total_score:.2f}/{max_total_score:.2f}")
        logger.info(f"  得分率: {score_percent:.1f}%")
        logger.info(f"  废标风险: {'有' if disqualification_risk else '无'}")
        logger.info(f"  高风险项: {risk_summary.get('high_risk_count', 0)}个")
        logger.info(f"  中风险项: {risk_summary.get('medium_risk_count', 0)}个")
        logger.info(f"  {'='*50}")

        total_elapsed = time.time() - start_time
        logger.info(f"[Stage 4] 评分完成, 耗时{total_elapsed:.2f}秒")

        return ScoringCard(
            tender_id=checklist.tender_id,
            bid_id=compliance_result.bid_id,
            total_score=round(total_score, 2),
            max_total_score=max_total_score,
            score_percent=round(score_percent, 2),
            dimensions=dimensions,
            risk_summary=risk_summary,
            disqualification_risk=disqualification_risk,
            disqualification_reasons=disqualification_reasons,
        )

    def _score_dimension(
        self,
        dim_name: str,
        dim_config: Dict[str, Any],
        checklist: TenderChecklist,
        compliance_result: ComplianceResult,
    ) -> DimensionScore:
        """
        计算单个维度的得分
        """
        weight = dim_config.get("weight", 0.0)
        max_score = dim_config.get("max_score", 0.0)
        items_source = dim_config.get("items_source", [])

        # 获取相关核对结果
        relevant_checks = [
            c for c in compliance_result.checks
            if self._check_matches_sources(c, checklist, items_source)
        ]

        total_items = len(relevant_checks)
        if total_items == 0:
            # 没有相关项目，给满分或0分取决于配置
            return DimensionScore(
                dimension=dim_name,
                weight=weight,
                max_score=max_score,
                actual_score=0.0,
                item_count=0,
                passed_count=0,
                failed_count=0,
                risk_items=[],
            )

        # 计算通过/失败数量
        passed_count = sum(
            1 for c in relevant_checks
            if c.hard_result and c.hard_result.status == "符合"
        )

        failed_count = total_items - passed_count

        # 计算实际得分
        if total_items > 0:
            pass_rate = passed_count / total_items
            actual_score = max_score * pass_rate
        else:
            actual_score = 0.0

        # 风险项目
        risk_items = [
            c.item_id for c in relevant_checks
            if c.final_risk_level in ["高", "极高"]
        ]

        return DimensionScore(
            dimension=dim_name,
            weight=weight,
            max_score=max_score,
            actual_score=round(actual_score, 2),
            item_count=total_items,
            passed_count=passed_count,
            failed_count=failed_count,
            risk_items=risk_items,
        )

    def _check_matches_sources(
        self,
        check: ComplianceCheck,
        checklist: TenderChecklist,
        sources: List[str],
    ) -> bool:
        """检查核对项是否匹配源类型"""
        # 找到对应的条款
        item = next(
            (i for i in checklist.items if i.item_id == check.item_id),
            None
        )

        if not item:
            return False

        # 检查类型匹配
        for source in sources:
            if source in item.type:
                return True
            if source == "硬性指标" and item.type == "硬性指标":
                return True
            if source == "评分项-技术" and item.type == "评分项":
                return True

        return False

    def _check_disqualification(
        self,
        compliance_result: ComplianceResult,
    ) -> Tuple[bool, List[str]]:
        """
        检测废标风险

        规则：
        1. 硬性指标不满足且标记为"废标"
        2. 关键资质未提供
        """
        reasons = []

        for check in compliance_result.checks:
            # 硬性指标不满足且废标
            if (
                check.hard_result
                and check.hard_result.status == "不符合"
                and check.hard_result.penalty_type == "废标"
            ):
                reasons.append(
                    f"条款{check.item_id}: 硬性指标不满足({check.hard_result.target_value})，"
                    f"实际值{check.hard_result.bid_value}"
                )

        return len(reasons) > 0, reasons

    def _summarize_risks(self, compliance_result: ComplianceResult) -> Dict[str, Any]:
        """风险汇总"""
        high_risk = []
        medium_risk = []

        for check in compliance_result.checks:
            if check.final_risk_level in ["高", "极高"]:
                high_risk.append(check.item_id)
            elif check.final_risk_level == "中":
                medium_risk.append(check.item_id)

        return {
            "high_risk_count": len(high_risk),
            "medium_risk_count": len(medium_risk),
            "high_risk_items": high_risk,
            "medium_risk_items": medium_risk,
        }

