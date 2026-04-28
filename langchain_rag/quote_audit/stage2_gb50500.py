"""
Layer 2: GB 50500合规检查
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .config import FEATURE_RULES, ITEM_TYPE_KEYWORDS, STANDARD_UNITS
from .models import ComplianceFinding, PipelineContext
from .remark_parser import RemarkParser


class Stage2GB50500:
    """进行单位规范、特征完整性与甲供规则检查。"""

    def __init__(self) -> None:
        self.remark_parser = RemarkParser()

    def run(self, context: PipelineContext) -> Tuple[PipelineContext, List[Dict]]:
        findings: List[ComplianceFinding] = []
        alerts: List[Dict] = []

        for item in context.items:
            item_type = self._infer_item_type(item.item_name)

            unit_finding = self._check_unit(item_type, item.unit, item.item_name, item.sequence)
            if unit_finding:
                findings.append(unit_finding)

            feature_finding = self._check_features(item_type, item.item_features, item.item_name, item.sequence)
            if feature_finding:
                findings.append(feature_finding)

            owner_supply_alerts = self.remark_parser.validate_owner_supply(item)
            for alert in owner_supply_alerts:
                findings.append(
                    ComplianceFinding(
                        item_sequence=item.sequence,
                        item_name=item.item_name,
                        finding_type="owner_supply_pricing",
                        severity=alert.get("severity", "warning"),
                        message=alert.get("message", "甲供设备校验异常"),
                        details=alert,
                    )
                )

        context.compliance_findings = findings

        for finding in findings:
            alerts.append(
                {
                    "type": "合规检查",
                    "severity": finding.severity,
                    "item": finding.item_name,
                    "message": finding.message,
                    "suggestion": self._suggestion_for(finding.finding_type),
                }
            )

        return context, alerts

    def _check_unit(self, item_type: str, unit: str, item_name: str, item_sequence: str):
        valid_units = STANDARD_UNITS.get(item_type, STANDARD_UNITS["其他"])
        if unit and unit in valid_units:
            return None

        return ComplianceFinding(
            item_sequence=item_sequence,
            item_name=item_name,
            finding_type="unit_inconsistency",
            severity="warning",
            message=f"计量单位不规范，当前单位={unit or '空'}，建议单位={valid_units}",
            details={"item_type": item_type, "unit": unit, "valid_units": valid_units},
        )

    def _check_features(self, item_type: str, features_text: str, item_name: str, item_sequence: str):
        required = FEATURE_RULES.get(item_type, [])
        if not required:
            return None

        text = (features_text or "").strip()
        missing = [feature for feature in required if feature not in text]
        if not missing:
            return None

        severity = "major" if len(missing) >= 3 else "warning"
        return ComplianceFinding(
            item_sequence=item_sequence,
            item_name=item_name,
            finding_type="feature_incomplete",
            severity=severity,
            message=f"项目特征不完整，缺失: {', '.join(missing)}",
            details={"item_type": item_type, "missing_features": missing},
        )

    def _infer_item_type(self, item_name: str) -> str:
        text = (item_name or "").upper()
        for item_type, keywords in ITEM_TYPE_KEYWORDS.items():
            if any(keyword.upper() in text for keyword in keywords):
                return item_type
        return "其他"

    def _suggestion_for(self, finding_type: str) -> str:
        suggestion_map = {
            "unit_inconsistency": "按GB 50500规范修正计量单位",
            "feature_incomplete": "补充项目特征必填信息",
            "owner_supply_pricing": "核对甲供设备主材/人工计价规则",
        }
        return suggestion_map.get(finding_type, "请人工复核该问题")
