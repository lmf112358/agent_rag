"""
报价审核Pipeline入口
"""

from __future__ import annotations

from time import perf_counter
from typing import Dict, List, Optional

from .logger import setup_logger
from .models import PipelineContext, QuoteAuditReport
from .stage1_cleansing import Stage1Cleansing
from .stage2_gb50500 import Stage2GB50500
from .stage3_arithmetic import Stage3Arithmetic
from .stage4_cost_index import Stage4CostIndex
from .stage5_report import Stage5Report


class QuoteAuditPipeline:
    """5层报价审核Pipeline。"""

    def __init__(self) -> None:
        self.logger = setup_logger("quote_audit")
        self.stage1 = Stage1Cleansing()
        self.stage2 = Stage2GB50500()
        self.stage3 = Stage3Arithmetic()
        self.stage4 = Stage4CostIndex()
        self.stage5 = Stage5Report()

    def run(
        self,
        excel_path: str,
        project_name: str,
        total_rt: Optional[float] = None,
        building_area: Optional[float] = None,
    ) -> QuoteAuditReport:
        context = PipelineContext(
            excel_path=excel_path,
            project_name=project_name,
            total_rt=total_rt,
            building_area=building_area,
        )
        stage_alerts: List[Dict] = []

        t1 = perf_counter()
        context, alerts = self.stage1.run(context)
        context.stage_times["stage1_cleansing"] = perf_counter() - t1
        stage_alerts.extend(alerts)
        self.logger.info("Stage1完成: items=%s alerts=%s", len(context.items), len(alerts))

        t2 = perf_counter()
        context, alerts = self.stage2.run(context)
        context.stage_times["stage2_gb50500"] = perf_counter() - t2
        stage_alerts.extend(alerts)
        self.logger.info("Stage2完成: findings=%s alerts=%s", len(context.compliance_findings), len(alerts))

        t3 = perf_counter()
        context, alerts = self.stage3.run(context)
        context.stage_times["stage3_arithmetic"] = perf_counter() - t3
        stage_alerts.extend(alerts)
        self.logger.info("Stage3完成: errors=%s alerts=%s", len(context.arithmetic_errors), len(alerts))

        t4 = perf_counter()
        context, alerts = self.stage4.run(context)
        context.stage_times["stage4_cost_index"] = perf_counter() - t4
        stage_alerts.extend(alerts)
        self.logger.info("Stage4完成: indices=%s alerts=%s", len(context.cost_indices), len(alerts))

        t5 = perf_counter()
        context, report = self.stage5.run(context, stage_alerts)
        context.stage_times["stage5_report"] = perf_counter() - t5
        self.logger.info("Stage5完成: issues=%s status=%s", len(report.issues), report.overall_status)

        return report
