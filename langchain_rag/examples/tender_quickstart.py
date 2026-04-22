"""
标书审核Agent - 快速开始示例

最简单的使用方式，3行代码运行完整审核Pipeline。
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_rag.tender_compliance import TenderCompliancePipeline


def main():
    """
    快速开始示例

    使用前请确保：
    1. MinerU服务已启动（默认 http://localhost:8008）
    2. 准备招标书PDF和投标书PDF
    """

    # 初始化Pipeline
    pipeline = TenderCompliancePipeline()

    # 运行完整审核流程
    # 注意：请将路径替换为实际的PDF文件路径
    report = pipeline.run(
        tender_pdf="data/samples/tender/tender_sample.pdf",  # 招标书PDF路径
        bid_pdf="data/samples/bid/bid_sample.pdf",          # 投标书PDF路径
        project_name="演示项目-高效机房",                 # 项目名称
        project_type="高效机房",                        # 项目类型
        company_name="示例公司",                        # 投标公司名称
    )

    # 输出审核结果
    print("\n" + "=" * 60)
    print("标书审核报告")
    print("=" * 60)
    print(f"报告ID: {report.report_id}")
    print(f"项目名称: {report.project_name}")
    print(f"\n评分结果:")
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

    return report


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║              标书审核Agent - 快速开始示例                     ║
║                                                              ║
║  本示例展示如何使用TenderCompliancePipeline运行完整审核流程   ║
╚══════════════════════════════════════════════════════════════╝
""")

    try:
        report = main()
        print("\n✅ 审核完成！")
    except FileNotFoundError as e:
        print(f"\n⚠️  文件未找到: {e}")
        print("\n请准备测试文件或修改路径后重试。")
        print("或使用模拟演示: python examples/tender_compliance_demo.py")
    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        import traceback
        traceback.print_exc()
