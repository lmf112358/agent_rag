"""
标书审核Agent - 完整演示脚本

支持两种模式：
1. 模拟模式（默认）：无需PDF文件，演示Pipeline流程
2. 真实模式（--with-files）：使用真实PDF文件运行
"""

import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def run_mock_mode():
    """
    模拟模式运行演示

    创建模拟数据来演示Pipeline流程
    """
    from langchain_rag.tender_compliance import (
        TenderChecklist,
        BidResponse,
        ComplianceResult,
        ScoringCard,
        ReviewReport,
    )
    from langchain_rag.tender_compliance.models import (
        TenderItem,
        ComplianceCheck,
        HardCheckResult,
        SoftCheckResult,
        KBVerifyResult,
        DimensionScore,
        ReviewDecision,
        MetricSpec,
    )

    logger.info("=" * 60)
    logger.info("模拟模式演示（无需PDF文件）")
    logger.info("=" * 60)

    # 创建模拟数据
    checklist = TenderChecklist(
        tender_id="TENDER_MOCK_001",
        project_name="珠海某PCB厂高效机房项目",
        project_type="高效机房",
        items=[
            TenderItem(
                item_id="ITEM_001",
                sequence="1.1",
                section_id="SEC_TECH",
                type="硬性指标",
                content="冷水机组额定COP≥6.0",
                quantifiable=True,
                metric=MetricSpec(
                    parameter="COP",
                    operator=">=",
                    target_value=6.0,
                    unit="",
                ),
                keywords=["COP", "冷水机组", "额定"],
                penalty_type="废标",
                confidence=0.9,
            ),
            TenderItem(
                item_id="ITEM_002",
                sequence="1.2",
                section_id="SEC_TECH",
                type="硬性指标",
                content="综合部分负荷性能系数IPLV≥9.0",
                quantifiable=True,
                metric=MetricSpec(
                    parameter="IPLV",
                    operator=">=",
                    target_value=9.0,
                    unit="",
                ),
                keywords=["IPLV", "综合部分负荷", "性能系数"],
                penalty_type="废标",
                confidence=0.9,
            ),
            TenderItem(
                item_id="ITEM_003",
                sequence="1.3",
                section_id="SEC_TECH",
                type="评分项",
                content="提供完整的系统设计方案",
                quantifiable=False,
                keywords=["技术方案", "设计方案", "完整"],
                score_weight=0.2,
                confidence=0.85,
            ),
            TenderItem(
                item_id="ITEM_004",
                sequence="2.1",
                section_id="SEC_QUAL",
                type="评分项",
                content="具有3个以上同类项目经验",
                quantifiable=False,
                keywords=["项目经验", "同类项目", "案例"],
                score_weight=0.15,
                confidence=0.85,
            ),
        ]
    )

    bid_response = BidResponse(
        bid_id="BID_MOCK_001",
        tender_id="TENDER_MOCK_001",
        project_name="珠海某PCB厂高效机房项目",
        equipment_tables=[],
        deviation_table={},
        technical_proposal={},
        qualification_docs=[],
    )

    compliance_result = ComplianceResult(
        bid_id="BID_MOCK_001",
        tender_id="TENDER_MOCK_001",
        checks=[
            ComplianceCheck(
                item_id="ITEM_001",
                check_type="Hard",
                hard_result=HardCheckResult(
                    status="符合",
                    deviation_type="符合",
                    target_value=6.0,
                    bid_value=6.5,
                    operator=">=",
                    risk_level="低",
                    penalty_type=None,
                    action="通过",
                ),
                soft_result=None,
                kb_result=None,
                final_status="符合",
                final_risk_level="低",
            ),
            ComplianceCheck(
                item_id="ITEM_002",
                check_type="Hard",
                hard_result=HardCheckResult(
                    status="符合",
                    deviation_type="符合",
                    target_value=9.0,
                    bid_value=9.2,
                    operator=">=",
                    risk_level="低",
                    penalty_type=None,
                    action="通过",
                ),
                soft_result=None,
                kb_result=None,
                final_status="符合",
                final_risk_level="低",
            ),
            ComplianceCheck(
                item_id="ITEM_003",
                check_type="Soft",
                hard_result=None,
                soft_result=SoftCheckResult(
                    is_responded="是",
                    response_quality="良",
                    suggested_score=85,
                    max_score=100,
                    confidence=0.85,
                    reasoning="技术方案完整，覆盖了所有关键要点",
                    evidence="提供了完整的系统设计方案文档",
                    needs_manual_review=False,
                ),
                kb_result=None,
                final_status="符合",
                final_risk_level="中",
            ),
            ComplianceCheck(
                item_id="ITEM_004",
                check_type="Soft",
                hard_result=None,
                soft_result=SoftCheckResult(
                    is_responded="是",
                    response_quality="优",
                    suggested_score=90,
                    max_score=100,
                    confidence=0.9,
                    reasoning="提供了5个同类项目案例，经验丰富",
                    evidence="提供了5个PCB厂高效机房项目案例",
                    needs_manual_review=False,
                ),
                kb_result=None,
                final_status="符合",
                final_risk_level="低",
            ),
        ],
        summary={
            "total_checks": 4,
            "passed": 4,
            "failed": 0,
            "needs_review": 0,
        }
    )

    # 计算评分卡
    scoring_card = ScoringCard(
        tender_id="TENDER_MOCK_001",
        bid_id="BID_MOCK_001",
        total_score=88.5,
        max_total_score=100.0,
        score_percent=88.5,
        dimensions=[
            DimensionScore(
                dimension="技术响应性",
                weight=0.4,
                max_score=40,
                actual_score=38,
                item_count=2,
                passed_count=2,
                failed_count=0,
                risk_items=[],
            ),
            DimensionScore(
                dimension="技术先进性",
                weight=0.2,
                max_score=20,
                actual_score=17,
                item_count=1,
                passed_count=1,
                failed_count=0,
                risk_items=[],
            ),
            DimensionScore(
                dimension="实施能力",
                weight=0.2,
                max_score=20,
                actual_score=18,
                item_count=1,
                passed_count=1,
                failed_count=0,
                risk_items=[],
            ),
            DimensionScore(
                dimension="服务保障",
                weight=0.2,
                max_score=20,
                actual_score=15.5,
                item_count=0,
                passed_count=0,
                failed_count=0,
                risk_items=[],
            ),
        ],
        risk_summary={
            "high_risk_count": 0,
            "medium_risk_count": 1,
            "high_risk_items": [],
            "medium_risk_items": ["ITEM_003"],
        },
        disqualification_risk=False,
        disqualification_reasons=[],
    )

    # 生成报告
    report = ReviewReport(
        report_id="REPORT_MOCK_20260420_001",
        tender_id="TENDER_MOCK_001",
        bid_id="BID_MOCK_001",
        project_name="珠海某PCB厂高效机房项目",
        company_name="示例投标公司",
        checklist=checklist,
        bid_response=bid_response,
        compliance_result=compliance_result,
        scoring_card=scoring_card,
        review_decisions=[
            ReviewDecision(
                item_id="ITEM_001",
                auto_decision="自动通过",
                confidence=0.95,
            ),
            ReviewDecision(
                item_id="ITEM_002",
                auto_decision="自动通过",
                confidence=0.95,
            ),
            ReviewDecision(
                item_id="ITEM_003",
                auto_decision="需人工确认",
                confidence=0.85,
            ),
            ReviewDecision(
                item_id="ITEM_004",
                auto_decision="自动通过",
                confidence=0.9,
            ),
        ],
        final_report={
            "triage_result": {
                "auto_pass": 3,
                "need_confirm": 1,
                "force_review": 0,
            },
            "summary": "标书整体符合要求，技术指标全部达标，建议优先考虑",
        },
    )

    # 输出结果
    print("\n" + "=" * 60)
    print("标书审核报告 (模拟模式)")
    print("=" * 60)
    print(f"报告ID: {report.report_id}")
    print(f"项目名称: {report.project_name}")
    if report.bid_response:
        print(f"投标公司: {report.bid_response.project_name}")
    print(f"\n评分结果:")
    if report.scoring_card:
        print(f"  总得分: {report.scoring_card.total_score:.2f}/{report.scoring_card.max_total_score}")
        print(f"  得分率: {report.scoring_card.score_percent:.1f}%")
        print(f"\n风险评估:")
        print(f"  废标风险: {'有' if report.scoring_card.disqualification_risk else '无'}")
        print(f"  高风险项: {report.scoring_card.risk_summary.get('high_risk_count', 0)} 个")
        print(f"  中风险项: {report.scoring_card.risk_summary.get('medium_risk_count', 0)} 个")
    print(f"\n分流结果:")
    triage = report.final_report.get("triage_result", {})
    print(f"  自动通过: {triage.get('auto_pass', 3)} 项")
    print(f"  需人工确认: {triage.get('need_confirm', 1)} 项")
    print(f"  强制人工审核: {triage.get('force_review', 0)} 项")
    print(f"\n审核结论: {report.final_report.get('summary', '标书整体符合要求')}")
    print("=" * 60)

    logger.info("模拟模式演示完成！")
    logger.info("")
    logger.info("如需使用真实PDF文件运行，请使用:")
    logger.info("  python examples/tender_compliance_demo.py --with-files")

    return report


def run_with_files():
    """
    真实模式运行演示

    使用真实PDF文件运行完整Pipeline
    """
    from langchain_rag.tender_compliance import TenderCompliancePipeline

    logger.info("=" * 60)
    logger.info("真实模式演示（使用PDF文件）")
    logger.info("=" * 60)

    # 初始化Pipeline（自动从.env读取配置）
    pipeline = TenderCompliancePipeline()

    # 运行完整审核流程
    report = pipeline.run(
        tender_pdf="data/samples/tender/tender_sample.pdf",
        bid_pdf="data/samples/bid/bid_sample.pdf",
        project_name="珠海某PCB厂高效机房项目",
        project_type="高效机房",
        company_name="示例投标公司",
    )

    # 输出结果
    print("\n" + "=" * 60)
    print("标书审核报告 (真实模式)")
    print("=" * 60)
    print(f"报告ID: {report.report_id}")
    print(f"项目名称: {report.project_name}")
    if report.bid_response:
        print(f"投标公司: {report.bid_response.project_name}")
    print(f"\n评分结果:")
    if report.scoring_card:
        print(f"  总得分: {report.scoring_card.total_score:.2f}/{report.scoring_card.max_total_score}")
        print(f"  得分率: {report.scoring_card.score_percent:.1f}%")
        print(f"\n风险评估:")
        print(f"  废标风险: {'有' if report.scoring_card.disqualification_risk else '无'}")
        print(f"  高风险项: {report.scoring_card.risk_summary.get('high_risk_count', 0)} 个")
        print(f"  中风险项: {report.scoring_card.risk_summary.get('medium_risk_count', 0)} 个")
    print(f"\n分流结果:")
    triage = report.final_report.get("triage_result", {})
    print(f"  自动通过: {triage.get('auto_pass', 0)} 项")
    print(f"  需人工确认: {triage.get('need_confirm', 0)} 项")
    print(f"  强制人工审核: {triage.get('force_review', 0)} 项")
    print("=" * 60)

    logger.info("真实模式演示完成！")
    return report


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="标书审核Agent演示")
    parser.add_argument(
        "--with-files",
        action="store_true",
        help="使用真实PDF文件运行（而非模拟模式）"
    )
    args = parser.parse_args()

    if args.with_files:
        return run_with_files()
    else:
        return run_mock_mode()


if __name__ == "__main__":
    print("""
================================================================
              标书审核Agent - 完整演示
================================================================
  本演示展示标书审核Pipeline的完整流程
================================================================
""")

    try:
        report = main()
        print("\n[OK] 演示完成！")
    except FileNotFoundError as e:
        print(f"\n[WARN] 文件未找到: {e}")
        print("\n请准备测试文件或修改路径后重试。")
        print("或使用模拟演示: python examples/tender_compliance_demo.py")
    except Exception as e:
        print(f"\n[ERROR] 运行出错: {e}")
        import traceback
        traceback.print_exc()
