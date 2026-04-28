"""
Layer 4: 造价指标分析 + 历史价格对比
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Tuple

from .config import COST_INDEX_THRESHOLDS, HISTORICAL_DEVIATION_THRESHOLD
from .models import CostIndexResult, PipelineContext, BillItem
from .historical_price import get_historical_price_store, PriceComparison


class Stage4CostIndex:
    """计算单方造价、占比并进行历史偏差告警，同时进行历史价格对比。"""

    # 价格偏离阈值
    PRICE_DEVIATION_THRESHOLD = Decimal("0.20")  # 20% 偏差

    def run(self, context: PipelineContext) -> Tuple[PipelineContext, List[Dict]]:
        results: List[CostIndexResult] = []
        alerts: List[Dict] = []

        historical_baseline = self._mock_historical_baseline()

        # 获取历史价格存储
        price_store = get_historical_price_store(use_mock=True)

        # 存储价格对比结果
        price_comparisons: List[PriceComparison] = []

        # 对每个清单项进行历史价格对比
        for item in context.items:
            if item.material_unit_price and item.material_unit_price > 0:
                comparison = self._compare_with_historical(item, price_store)
                if comparison:
                    price_comparisons.append(comparison)

                    # 生成告警
                    alerts.append({
                        "type": "历史价格对比",
                        "severity": comparison.severity,
                        "item": item.item_name,
                        "expected": str(comparison.historical_avg_price) if comparison.historical_avg_price else None,
                        "actual": str(comparison.current_price) if comparison.current_price else None,
                        "message": comparison.message,
                        "suggestion": comparison.suggestion,
                    })

        # 按分部汇总
        for summary in context.summaries:
            grand_total = summary.grand_total or Decimal("0")
            if grand_total == 0:
                continue

            material_ratio = (summary.subtotal_material / grand_total) if summary.subtotal_material else Decimal("0")
            labor_ratio = (summary.subtotal_labor / grand_total) if summary.subtotal_labor else Decimal("0")
            measures_ratio = (summary.measures_cost / grand_total) if summary.measures_cost else Decimal("0")
            tax_ratio = (summary.tax / grand_total) if summary.tax else Decimal("0")

            unit_cost_per_rt = None
            if context.total_rt and context.total_rt > 0:
                unit_cost_per_rt = grand_total / context.total_rt

            unit_cost_per_sqm = None
            if context.building_area and context.building_area > 0:
                unit_cost_per_sqm = grand_total / context.building_area

            ratio_alerts = self._check_ratio_alerts(material_ratio, labor_ratio)
            deviation = self._historical_deviation(material_ratio, historical_baseline["material_ratio"])

            historical_comparison = {
                "baseline_material_ratio": str(historical_baseline["material_ratio"]),
                "current_material_ratio": str(material_ratio),
                "deviation": str(deviation),
                "price_comparisons_count": len(price_comparisons),
            }

            if abs(deviation) > HISTORICAL_DEVIATION_THRESHOLD:
                ratio_alerts.append({
                    "type": "历史对标偏差",
                    "severity": "warning",
                    "message": f"材料占比相对历史偏差过大，偏差={float(deviation)*100:.1f}%",
                    "suggestion": "核查主材价格或成本结构变化原因",
                })

            result = CostIndexResult(
                phase=summary.phase,
                unit_cost_per_rt=unit_cost_per_rt,
                unit_cost_per_sqm=unit_cost_per_sqm,
                material_ratio=material_ratio,
                labor_ratio=labor_ratio,
                measures_ratio=measures_ratio,
                tax_ratio=tax_ratio,
                alerts=ratio_alerts,
                historical_comparison=historical_comparison,
            )
            results.append(result)

            for alert in ratio_alerts:
                alerts.append({
                    "type": "造价指标",
                    "severity": alert.get("severity", "warning"),
                    "item": summary.phase,
                    "message": alert.get("message", "指标异常"),
                    "suggestion": alert.get("suggestion", "请人工复核"),
                })

        context.cost_indices = results
        # 将价格对比结果存入 context（绕过 Pydantic 验证）
        object.__setattr__(context, 'price_comparisons', price_comparisons)
        return context, alerts

    def _compare_with_historical(
        self,
        item: BillItem,
        price_store
    ) -> Optional[PriceComparison]:
        """将清单项与历史价格对比"""
        current_price = item.material_unit_price

        # 查询历史价格
        historical_prices = price_store.query_historical_prices(
            equipment_name=item.item_name,
            model_spec=item.model_spec,
            top_k=5
        )

        if not historical_prices:
            return None

        # 计算历史平均价格
        hist_avg = sum(p.unit_price for p in historical_prices) / len(historical_prices)

        # 计算偏差
        if hist_avg > 0:
            deviation = (current_price - hist_avg) / hist_avg
            deviation_percent = float(deviation * 100)
        else:
            deviation_percent = 0.0

        # 判断严重程度
        abs_deviation = abs(deviation_percent)
        if abs_deviation > 50:
            severity = "fatal"
            severity_text = "🔴 严重偏离"
        elif abs_deviation > 30:
            severity = "major"
            severity_text = "🟠 较大偏离"
        elif abs_deviation > 20:
            severity = "warning"
            severity_text = "🟡 轻度偏离"
        else:
            severity = "info"
            severity_text = "ℹ️ 正常范围"

        # 生成消息
        if deviation_percent > 0:
            message = f"当前报价({float(current_price):,.2f}元)高于历史均价({float(hist_avg):,.2f}元) {deviation_percent:.1f}%"
        else:
            message = f"当前报价({float(current_price):,.2f}元)低于历史均价({float(hist_avg):,.2f}元) {abs(deviation_percent):.1f}%"

        suggestion = "核查报价合理性，需提供价格依据" if abs_deviation > 20 else "价格处于正常范围"

        return PriceComparison(
            item_name=item.item_name,
            current_price=current_price,
            historical_avg_price=hist_avg,
            deviation_percent=deviation_percent,
            historical_prices=historical_prices,
            severity=severity,
            message=message,
            suggestion=suggestion,
        )

    def _check_ratio_alerts(self, material_ratio: Decimal, labor_ratio: Decimal) -> List[Dict]:
        alerts: List[Dict] = []

        material_cfg = COST_INDEX_THRESHOLDS["material_ratio"]
        if material_ratio < material_cfg["low"]:
            alerts.append({
                "type": "材料费占比偏低",
                "severity": "warning",
                "message": f"材料费占比偏低，当前={float(material_ratio)*100:.1f}%",
                "suggestion": "核查甲供标记、漏项或人工费过高情况",
            })
        elif material_ratio > material_cfg["high"]:
            alerts.append({
                "type": "材料费占比偏高",
                "severity": "warning",
                "message": f"材料费占比偏高，当前={float(material_ratio)*100:.1f}%",
                "suggestion": "核查材料单价合理性及人工费是否漏计",
            })

        labor_cfg = COST_INDEX_THRESHOLDS["labor_ratio"]
        if labor_ratio < labor_cfg["low"]:
            alerts.append({
                "type": "人工费占比偏低",
                "severity": "warning",
                "message": f"人工费占比偏低，当前={float(labor_ratio)*100:.1f}%",
                "suggestion": "核查人工费是否漏计",
            })
        elif labor_ratio > labor_cfg["high"]:
            alerts.append({
                "type": "人工费占比偏高",
                "severity": "warning",
                "message": f"人工费占比偏高，当前={float(labor_ratio)*100:.1f}%",
                "suggestion": "核查人工单价或工程量是否异常",
            })

        return alerts

    def _historical_deviation(self, current: Decimal, baseline: Decimal) -> Decimal:
        if baseline == 0:
            return Decimal("0")
        return (current - baseline) / baseline

    def _mock_historical_baseline(self) -> Dict[str, Decimal]:
        return {"material_ratio": Decimal("0.70")}
