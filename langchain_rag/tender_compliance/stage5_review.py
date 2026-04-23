"""
Stage 5: 人工复核层 (Human Review)

负责：
1. 自动分流决策（高/中/低风险分流）
2. 人工复核接口
3. 审核报告生成
4. 报告导出（JSON/PDF）
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from .models import (
    TenderDocument,
    BidDocument,
    TenderChecklist,
    BidResponse,
    ComplianceResult,
    ScoringCard,
    ReviewReport,
    ReviewDecision,
)
from .config import AUTO_DECISION_RULES, REPORT_TEMPLATE

logger = logging.getLogger(__name__)


class Stage5Review:
    """
    Stage 5: 人工复核层

    整合前4阶段结果，生成分流决策和审核报告
    """

    def __init__(
        self,
        high_confidence_threshold: float = 0.8,
        medium_confidence_threshold: float = 0.6,
        auto_pass_compliance_rate: float = 95.0,
        auto_fail_high_risk_count: int = 3,
    ):
        self.high_confidence_threshold = high_confidence_threshold
        self.medium_confidence_threshold = medium_confidence_threshold
        self.auto_pass_compliance_rate = auto_pass_compliance_rate
        self.auto_fail_high_risk_count = auto_fail_high_risk_count

    def generate_report(
        self,
        tender_doc: TenderDocument,
        bid_doc: BidDocument,
        checklist: TenderChecklist,
        bid_response: BidResponse,
        compliance_result: ComplianceResult,
        scoring_card: ScoringCard,
    ) -> ReviewReport:
        """
        生成完整审核报告

        Args:
            tender_doc: 招标书文档对象
            bid_doc: 投标书文档对象
            checklist: 招标书Checklist
            bid_response: 投标书响应
            compliance_result: 核对结果
            scoring_card: 评分卡

        Returns:
            ReviewReport: 完整审核报告
        """
        import time
        start_time = time.time()

        logger.info(f"[Stage 5] 开始生成审核报告")
        logger.info(f"  项目名称: {tender_doc.project_name}")
        logger.info(f"  投标公司: {bid_doc.company_name}")

        # 1. 生成每个条款的复核决策
        logger.info(f"  [1/2] 生成复核决策...")
        review_decisions = self._generate_review_decisions(
            compliance_result, scoring_card
        )

        auto_pass = sum(1 for d in review_decisions if d.auto_decision == "自动通过")
        need_confirm = sum(1 for d in review_decisions if d.auto_decision == "需人工确认")
        force_review = sum(1 for d in review_decisions if d.auto_decision == "强制人工审核")

        logger.info(f"    自动通过: {auto_pass}项")
        logger.info(f"    需人工确认: {need_confirm}项")
        logger.info(f"    强制人工审核: {force_review}项")
        if review_decisions:
            auto_rate = auto_pass / len(review_decisions) * 100
            logger.info(f"    自动通过率: {auto_rate:.1f}%")

        # 2. 生成最终报告
        logger.info(f"  [2/2] 生成最终报告...")
        final_report = self._generate_final_report(
            tender_doc, bid_doc, checklist, bid_response,
            compliance_result, scoring_card, review_decisions
        )

        report_id = f"REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        recommendation = final_report.get("overall_recommendation", "")

        logger.info(f"")
        logger.info(f"  {'='*60}")
        logger.info(f"  报告ID: {report_id}")
        logger.info(f"  复核项数: {len(review_decisions)}项")
        logger.info(f"  整体建议: {recommendation}")
        logger.info(f"  {'='*60}")

        total_elapsed = time.time() - start_time
        logger.info(f"[Stage 5] 报告生成完成, 耗时{total_elapsed:.2f}秒")

        return ReviewReport(
            report_id=report_id,
            tender_id=tender_doc.tender_id,
            bid_id=bid_doc.bid_id,
            project_name=tender_doc.project_name,
            checklist=checklist,
            bid_response=bid_response,
            compliance_result=compliance_result,
            scoring_card=scoring_card,
            review_decisions=review_decisions,
            final_report=final_report,
        )

    def _generate_review_decisions(
        self,
        compliance_result: ComplianceResult,
        scoring_card: ScoringCard,
    ) -> List[ReviewDecision]:
        """生成每个条款的复核决策"""
        decisions = []

        for check in compliance_result.checks:
            # 基于Hard/Soft/KB三层结果计算置信度
            confidence = self._calculate_confidence(check)

            # 基于置信度和结果生成分流决策
            auto_decision = self._determine_auto_decision(
                check, confidence, scoring_card
            )

            decision = ReviewDecision(
                item_id=check.item_id,
                auto_decision=auto_decision,
                confidence=round(confidence, 2),
            )
            decisions.append(decision)

        return decisions

    def _calculate_confidence(self, check: Any) -> float:
        """计算核对结果置信度"""
        confidences = []

        # Hard Check置信度（纯数值计算，置信度最高）
        if check.hard_result:
            if check.hard_result.status in ["符合", "不符合"]:
                confidences.append(0.95)
            else:
                confidences.append(0.5)

        # Soft Check置信度
        if check.soft_result:
            confidences.append(check.soft_result.confidence)

        # KB Verify置信度
        if check.kb_result:
            if check.kb_result.model_found:
                confidences.append(0.9)
            else:
                confidences.append(0.6)

        # 综合置信度
        if confidences:
            return sum(confidences) / len(confidences)
        return 0.0

    def _determine_auto_decision(
        self,
        check: Any,
        confidence: float,
        scoring_card: ScoringCard,
    ) -> str:
        """
        确定自动分流决策

        决策逻辑：
        1. 极高风险 → 强制人工审核
        2. 高置信度+符合 → 自动通过
        3. 高置信度+不符合+废标 → 强制人工审核
        4. 中置信度 → 需人工确认
        5. 低置信度 → 需人工确认
        """
        # 极高风险强制人工审核
        if check.final_risk_level in ["高", "极高"]:
            if check.hard_result and check.hard_result.penalty_type == "废标":
                return "强制人工审核"
            return "需人工确认"

        # 高置信度
        if confidence >= self.high_confidence_threshold:
            if check.final_status == "符合":
                return "自动通过"
            else:
                return "需人工确认"

        # 中置信度
        if confidence >= self.medium_confidence_threshold:
            return "需人工确认"

        # 低置信度
        return "需人工确认"

    def _generate_final_report(
        self,
        tender_doc: TenderDocument,
        bid_doc: BidDocument,
        checklist: TenderChecklist,
        bid_response: BidResponse,
        compliance_result: ComplianceResult,
        scoring_card: ScoringCard,
        review_decisions: List[ReviewDecision],
    ) -> Dict[str, Any]:
        """生成最终汇总报告"""

        # 分流统计
        auto_pass = sum(1 for d in review_decisions if d.auto_decision == "自动通过")
        need_confirm = sum(1 for d in review_decisions if d.auto_decision == "需人工确认")
        force_review = sum(1 for d in review_decisions if d.auto_decision == "强制人工审核")

        # 整体建议
        overall_recommendation = self._generate_overall_recommendation(
            scoring_card, review_decisions
        )

        return {
            "project_info": {
                "project_name": tender_doc.project_name,
                "project_type": tender_doc.project_type,
                "tender_id": tender_doc.tender_id,
                "bid_id": bid_doc.bid_id,
                "company_name": bid_doc.company_name,
            },
            "summary": {
                "total_items": len(checklist.items),
                "hard_requirements": sum(1 for i in checklist.items if i.type == "硬性指标"),
                "scoring_items": sum(1 for i in checklist.items if i.type == "评分项"),
                "compliance_rate": compliance_result.summary.get("compliance_rate", 0),
                "total_score": scoring_card.total_score,
                "max_score": scoring_card.max_total_score,
                "score_percent": scoring_card.score_percent,
            },
            "risk_assessment": {
                "disqualification_risk": scoring_card.disqualification_risk,
                "disqualification_reasons": scoring_card.disqualification_reasons,
                "high_risk_count": scoring_card.risk_summary.get("high_risk_count", 0),
                "medium_risk_count": scoring_card.risk_summary.get("medium_risk_count", 0),
            },
            "triage_result": {
                "auto_pass": auto_pass,
                "need_confirm": need_confirm,
                "force_review": force_review,
                "auto_pass_rate": round(auto_pass / len(review_decisions) * 100, 1) if review_decisions else 0,
            },
            "overall_recommendation": overall_recommendation,
            "review_status": "pending",  # pending/completed
            "generated_at": datetime.now().isoformat(),
        }

    def _generate_overall_recommendation(
        self,
        scoring_card: ScoringCard,
        review_decisions: List[ReviewDecision],
    ) -> str:
        """生成整体建议"""

        # 有废标风险
        if scoring_card.disqualification_risk:
            return "存在废标风险项，建议人工重点审核"

        # 评分过低
        if scoring_card.score_percent < 60:
            return "整体评分较低，建议综合评估"

        # 高风险项过多
        high_risk = scoring_card.risk_summary.get("high_risk_count", 0)
        if high_risk >= self.auto_fail_high_risk_count:
            return f"存在{high_risk}项高风险项，建议人工审核"

        # 自动通过率
        auto_pass = sum(1 for d in review_decisions if d.auto_decision == "自动通过")
        if len(review_decisions) > 0 and auto_pass / len(review_decisions) >= 0.8:
            return "自动审核通过率高，建议快速通过"

        return "建议常规人工复核"

    def export_report(
        self,
        report: ReviewReport,
        output_dir: str,
        format: str = "json",
    ) -> str:
        """
        导出审核报告

        Args:
            report: 审核报告
            output_dir: 输出目录
            format: 格式 (json/pdf/html)

        Returns:
            str: 导出文件路径
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        if format == "json":
            return self._export_json(report, output_path)
        elif format == "html":
            return self._export_html(report, output_path)
        else:
            raise ValueError(f"不支持的导出格式: {format}")

    def _export_json(self, report: ReviewReport, output_path: Path) -> str:
        """导出JSON格式报告"""
        import json

        file_path = output_path / f"{report.report_id}.json"

        # 转换为可JSON序列化的字典
        report_dict = report.model_dump(mode="json", exclude_none=True)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, ensure_ascii=False, indent=2)

        logger.info(f"报告已导出: {file_path}")
        return str(file_path)

    def _export_html(self, report: ReviewReport, output_path: Path) -> str:
        """导出HTML格式报告"""
        file_path = output_path / f"{report.report_id}.html"

        # 简化HTML模板
        html_content = self._generate_html_report(report)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"HTML报告已导出: {file_path}")
        return str(file_path)

    def _generate_html_report(self, report: ReviewReport) -> str:
        """生成HTML报告内容"""

        final = report.final_report
        summary = final.get("summary", {})
        risk = final.get("risk_assessment", {})
        triage = final.get("triage_result", {})

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>标书审核报告 - {final.get("project_info", {}).get("project_name", "")}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #0066cc; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .section {{ background: #f9f9f9; padding: 20px; margin: 20px 0; border-radius: 5px; }}
        .highlight {{ background: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 15px 0; }}
        .danger {{ background: #f8d7da; border-left-color: #dc3545; }}
        .success {{ background: #d4edda; border-left-color: #28a745; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #0066cc; color: white; }}
        .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #0066cc; }}
        .metric-label {{ font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>标书审核报告</h1>

        <div class="section">
            <h2>项目信息</h2>
            <p><strong>项目名称:</strong> {final.get("project_info", {}).get("project_name", "N/A")}</p>
            <p><strong>项目类型:</strong> {final.get("project_info", {}).get("project_type", "N/A")}</p>
            <p><strong>投标公司:</strong> {final.get("project_info", {}).get("company_name", "N/A")}</p>
            <p><strong>报告ID:</strong> {report.report_id}</p>
            <p><strong>生成时间:</strong> {report.generated_at.strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>

        <div class="section">
            <h2>评分汇总</h2>
            <div class="metric">
                <div class="metric-value">{summary.get("score_percent", 0):.1f}%</div>
                <div class="metric-label">综合得分率</div>
            </div>
            <div class="metric">
                <div class="metric-value">{summary.get("total_score", 0):.1f}</div>
                <div class="metric-label">总分</div>
            </div>
            <div class="metric">
                <div class="metric-value">{summary.get("compliance_rate", 0):.1f}%</div>
                <div class="metric-label">合规率</div>
            </div>
        </div>

        <div class="section">
            <h2>风险评估</h2>
            {f'<div class="highlight danger"><strong>废标风险:</strong> 检测到废标风险项，请立即处理</div>' if risk.get("disqualification_risk") else '<div class="highlight success"><strong>废标风险:</strong> 无</div>'}
            <p><strong>高风险项:</strong> {risk.get("high_risk_count", 0)} 个</p>
            <p><strong>中风险项:</strong> {risk.get("medium_risk_count", 0)} 个</p>
        </div>

        <div class="section">
            <h2>分流结果</h2>
            <table>
                <tr><th>分流类型</th><th>数量</th><th>占比</th></tr>
                <tr><td>自动通过</td><td>{triage.get("auto_pass", 0)}</td><td>-</td></tr>
                <tr><td>需人工确认</td><td>{triage.get("need_confirm", 0)}</td><td>-</td></tr>
                <tr><td>强制人工审核</td><td>{triage.get("force_review", 0)}</td><td>-</td></tr>
            </table>
        </div>

        <div class="highlight">
            <h2>整体建议</h2>
            <p>{final.get("overall_recommendation", "")}</p>
        </div>
    </div>
</body>
</html>"""


class ReviewInterface:
    """
    人工复核接口

    供前端调用的人工复核API
    """

    def __init__(self):
        self.pending_reviews: Dict[str, ReviewDecision] = {}

    def get_pending_items(self, report: ReviewReport) -> List[ReviewDecision]:
        """获取待人工复核的条款"""
        return [
            d for d in report.review_decisions
            if d.auto_decision in ["需人工确认", "强制人工审核"]
            and d.final_decision is None
        ]

    def submit_review(
        self,
        report: ReviewReport,
        item_id: str,
        decision: str,
        reviewer: str,
        comment: Optional[str] = None,
    ) -> ReviewDecision:
        """提交人工复核结果"""

        for d in report.review_decisions:
            if d.item_id == item_id:
                d.final_decision = decision
                d.reviewer = reviewer
                d.review_time = datetime.now()
                d.review_comment = comment
                logger.info(f"人工复核完成: {item_id} -> {decision} (by {reviewer})")
                return d

        raise ValueError(f"未找到条款: {item_id}")

    def is_review_complete(self, report: ReviewReport) -> bool:
        """检查是否所有需复核项都已完成"""
        pending = self.get_pending_items(report)
        return len(pending) == 0

    def get_review_statistics(self, report: ReviewReport) -> Dict[str, Any]:
        """获取复核统计信息"""
        total = len(report.review_decisions)
        pending = len(self.get_pending_items(report))
        completed = total - pending

        return {
            "total_items": total,
            "completed": completed,
            "pending": pending,
            "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
        }
