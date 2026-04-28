"""
Layer 3: 算术校验引擎
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Tuple

from .config import DECIMAL_PRECISION, FEE_RATES, TOLERANCE
from .models import ArithmeticError, BillSummary, PipelineContext


class Stage3Arithmetic:
    """执行横向量价、纵向汇总与费用层级校验。"""

    def run(self, context: PipelineContext) -> Tuple[PipelineContext, List[Dict]]:
        errors: List[ArithmeticError] = []
        alerts: List[Dict] = []

        summary_by_phase: Dict[str, Dict[str, Decimal]] = {}

        for item in context.items:
            phase = item.phase or "未知"
            summary_by_phase.setdefault(
                phase,
                {
                    "subtotal_material": Decimal("0"),
                    "subtotal_labor": Decimal("0"),
                },
            )

            material_error = self._check_line_item(
                item_sequence=item.sequence,
                item_name=item.item_name,
                quantity=item.quantity,
                unit_price=item.material_unit_price,
                actual_total=item.material_total,
                error_type="material_mismatch",
            )
            if material_error:
                errors.append(material_error)

            labor_error = self._check_line_item(
                item_sequence=item.sequence,
                item_name=item.item_name,
                quantity=item.quantity,
                unit_price=item.labor_unit_price,
                actual_total=item.labor_total,
                error_type="labor_mismatch",
            )
            if labor_error:
                errors.append(labor_error)

            summary_by_phase[phase]["subtotal_material"] += item.material_total or Decimal("0")
            summary_by_phase[phase]["subtotal_labor"] += item.labor_total or Decimal("0")

        summaries: List[BillSummary] = []
        for phase, values in summary_by_phase.items():
            subtotal_material = self._q(values["subtotal_material"])
            subtotal_labor = self._q(values["subtotal_labor"])
            direct_cost = self._q(subtotal_material + subtotal_labor)
            measures_cost = self._q(direct_cost * FEE_RATES["measures_rate"])

            tax_base = direct_cost
            if FEE_RATES.get("tax_base") == "direct_plus_measures":
                tax_base = direct_cost + measures_cost

            tax = self._q(tax_base * FEE_RATES["tax_rate"])
            grand_total = self._q(direct_cost + measures_cost + tax)

            summaries.append(
                BillSummary(
                    phase=phase,
                    subtotal_material=subtotal_material,
                    subtotal_labor=subtotal_labor,
                    direct_cost=direct_cost,
                    measures_cost=measures_cost,
                    tax=tax,
                    grand_total=grand_total,
                )
            )

        context.summaries = summaries
        context.arithmetic_errors = errors

        for error in errors:
            severity = error.severity
            if error.error_type == "material_mismatch":
                alerts.append(
                    {
                        "type": "算术校验-主材合价",
                        "severity": severity,
                        "item": error.item_name,
                        "item_sequence": error.item_sequence,
                        "expected": str(error.expected) if error.expected else None,
                        "actual": str(error.actual) if error.actual else None,
                        "difference": str(error.difference) if error.difference else None,
                        "message": f"主材合价计算错误: 工程量×主材单价={float(error.expected):,.2f}，实际={float(error.actual):,.2f}，差异={float(error.difference):+,.2f}元",
                        "suggestion": f"修正主材合价，应为 {float(error.expected):,.2f} 元",
                    }
                )
            elif error.error_type == "labor_mismatch":
                alerts.append(
                    {
                        "type": "算术校验-人工合价",
                        "severity": severity,
                        "item": error.item_name,
                        "item_sequence": error.item_sequence,
                        "expected": str(error.expected) if error.expected else None,
                        "actual": str(error.actual) if error.actual else None,
                        "difference": str(error.difference) if error.difference else None,
                        "message": f"人工合价计算错误: 工程量×人工单价={float(error.expected):,.2f}，实际={float(error.actual):,.2f}，差异={float(error.difference):+,.2f}元",
                        "suggestion": f"修正人工合价，应为 {float(error.expected):,.2f} 元",
                    }
                )

        return context, alerts

    def _check_line_item(
        self,
        item_sequence: str,
        item_name: str,
        quantity: Decimal,
        unit_price: Decimal,
        actual_total: Decimal,
        error_type: str,
    ):
        if quantity is None or unit_price is None or actual_total is None:
            return None

        expected_total = self._q(quantity * unit_price)
        diff = self._q(actual_total - expected_total)
        if abs(diff) <= TOLERANCE:
            return None

        return ArithmeticError(
            item_sequence=item_sequence,
            item_name=item_name,
            error_type=error_type,
            expected=expected_total,
            actual=actual_total,
            difference=diff,
            severity="major",
        )

    def _q(self, value: Decimal) -> Decimal:
        return value.quantize(DECIMAL_PRECISION, rounding=ROUND_HALF_UP)
