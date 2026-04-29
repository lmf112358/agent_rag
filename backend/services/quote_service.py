"""
报价审核服务
"""
import os
import sys
import traceback
from pathlib import Path
from uuid import uuid4
from typing import Dict, Any, Optional, List

# 确保项目根目录在路径中
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langchain_rag.quote_audit import QuoteAuditPipeline
from langchain_rag.quote_audit.models import QuoteAuditReport

class QuoteAuditService:
    """报价审核服务 - 单例模式，避免重复初始化"""

    _instance: Optional["QuoteAuditService"] = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._error = None
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        print("[QuoteAuditService] 正在初始化...")
        try:
            # 初始化审核Pipeline
            self.pipeline = QuoteAuditPipeline()
            self._initialized = True
            print("[QuoteAuditService] 初始化完成")
        except Exception as e:
            self._error = str(e)
            print(f"[QuoteAuditService] 初始化失败: {self._error}")
            print(traceback.format_exc())

    def run_audit(
        self,
        excel_path: str,
        project_name: str,
        total_rt: Optional[float] = None,
        building_area: Optional[float] = None
    ) -> Dict[str, Any]:
        """执行报价审核"""
        if not self._initialized:
            return {
                "success": False,
                "error": f"服务初始化失败: {self._error}",
                "report": None
            }

        try:
            # 运行Pipeline
            report = self.pipeline.run(
                excel_path=excel_path,
                project_name=project_name,
                total_rt=total_rt,
                building_area=building_area
            )

            # 转换为可序列化格式
            return {
                "success": True,
                "error": None,
                "report": self._report_to_dict(report)
            }
        except Exception as e:
            print(f"[QuoteAuditService] 审核失败: {e}")
            print(traceback.format_exc())
            return {
                "success": False,
                "error": f"审核执行失败: {str(e)}",
                "report": None
            }

    def _report_to_dict(self, report: QuoteAuditReport) -> Dict[str, Any]:
        """将报告模型转换为可序列化字典"""
        return {
            "report_id": report.report_id,
            "project_name": report.project_name,
            "audit_time": report.audit_time.isoformat() if report.audit_time else None,
            "overall_status": report.overall_status,
            "total_items": report.total_items,
            "fatal_count": report.fatal_count,
            "major_count": report.major_count,
            "warning_count": report.warning_count,
            "info_count": report.info_count,
            "pass_rate": float(report.pass_rate),
            "cost_indices": [
                {
                    "phase": idx.phase,
                    "unit_cost_per_rt": float(idx.unit_cost_per_rt) if idx.unit_cost_per_rt else None,
                    "unit_cost_per_sqm": float(idx.unit_cost_per_sqm) if idx.unit_cost_per_sqm else None,
                    "material_ratio": float(idx.material_ratio),
                    "labor_ratio": float(idx.labor_ratio),
                    "alerts": idx.alerts,
                    "historical_comparison": idx.historical_comparison
                } for idx in report.cost_indices
            ],
            "issues": [
                {
                    "issue_id": issue.issue_id,
                    "severity": issue.severity,
                    "category": issue.category,
                    "location": issue.location,
                    "message": issue.message,
                    "suggestion": issue.suggestion
                } for issue in report.issues
            ],
            "recommendations": report.recommendations,
            "markdown": report.markdown,
            "summaries": [
                {
                    "phase": s.phase,
                    "subtotal_material": float(s.subtotal_material),
                    "subtotal_labor": float(s.subtotal_labor),
                    "direct_cost": float(s.direct_cost),
                    "measures_cost": float(s.measures_cost),
                    "tax": float(s.tax),
                    "grand_total": float(s.grand_total),
                } for s in report.summaries
            ],
            "sections": [
                {
                    "section_id": s.section_id,
                    "section_name": s.section_name,
                    "phase": s.phase,
                    "subtotal_material": float(s.subtotal_material),
                    "subtotal_labor": float(s.subtotal_labor),
                    "item_count": len(s.items),
                    "items": [
                        {
                            "sequence": item.sequence,
                            "item_name": item.item_name,
                            "item_features": item.item_features,
                            "unit": item.unit,
                            "quantity": float(item.quantity) if item.quantity else None,
                            "material_unit_price": float(item.material_unit_price) if item.material_unit_price else None,
                            "labor_unit_price": float(item.labor_unit_price) if item.labor_unit_price else None,
                            "material_total": float(item.material_total) if item.material_total else None,
                            "labor_total": float(item.labor_total) if item.labor_total else None,
                            "phase": item.phase,
                        } for item in s.items
                    ],
                    "errors": s.subtotal_errors,
                } for s in report.sections
            ],
            "compliance_findings": [
                {
                    "item_sequence": f.item_sequence,
                    "item_name": f.item_name,
                    "finding_type": f.finding_type,
                    "severity": f.severity,
                    "message": f.message,
                } for f in report.compliance_findings
            ],
            "arithmetic_errors": [
                {
                    "item_sequence": e.item_sequence,
                    "item_name": e.item_name,
                    "error_type": e.error_type,
                    "severity": e.severity,
                    "expected": float(e.expected) if e.expected else None,
                    "actual": float(e.actual) if e.actual else None,
                    "difference": float(e.difference) if e.difference else None,
                } for e in report.arithmetic_errors
            ],
            "total_rt": float(report.total_rt) if report.total_rt else None,
            "building_area": float(report.building_area) if report.building_area else None,
        }
