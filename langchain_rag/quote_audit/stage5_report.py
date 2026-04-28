"""
Layer 5: 风险预警与报告生成
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Tuple
from uuid import uuid4
from datetime import datetime

from .models import AuditIssue, PipelineContext, QuoteAuditReport


class Stage5Report:
    """汇总各层结果并生成最终报告。"""

    def run(self, context: PipelineContext, stage_alerts: List[Dict]) -> Tuple[PipelineContext, QuoteAuditReport]:
        issues = self._build_issues(stage_alerts)

        fatal_count = sum(1 for issue in issues if issue.severity == "fatal")
        major_count = sum(1 for issue in issues if issue.severity == "major")
        warning_count = sum(1 for issue in issues if issue.severity == "warning")
        info_count = sum(1 for issue in issues if issue.severity == "info")

        # 按唯一item统计（同一item可能有多个issues）
        total_items = len(context.items)
        item_severities: Dict[str, str] = {}  # item_location -> worst severity
        for alert in stage_alerts:
            loc = str(alert.get("item", ""))
            sev = alert.get("severity", "warning")
            if loc not in item_severities:
                item_severities[loc] = sev
            else:
                # 按严重程度排序：fatal > major > warning > info
                severity_order = {"fatal": 0, "major": 1, "warning": 2, "info": 3}
                if severity_order.get(sev, 99) < severity_order.get(item_severities[loc], 99):
                    item_severities[loc] = sev

        # 有问题的item数（按唯一item去重）
        items_with_fatal = sum(1 for sev in item_severities.values() if sev == "fatal")
        items_with_major = sum(1 for sev in item_severities.values() if sev == "major")
        items_with_warning = sum(1 for sev in item_severities.values() if sev == "warning")
        items_with_info = sum(1 for sev in item_severities.values() if sev == "info")

        # 唯一有问题item数（fatal和major必定算失败，warning/info视情况）
        # 简单策略：有任何fatal/major/warning的item都算有问题
        failed_items = sum(1 for sev in item_severities.values() if sev in ("fatal", "major", "warning"))
        failed_items = min(failed_items, total_items)

        pass_rate = Decimal("1")
        if total_items > 0:
            pass_rate = (Decimal(total_items - failed_items) / Decimal(total_items)).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )

        overall_status = self._determine_status(fatal_count, major_count)

        report = QuoteAuditReport(
            report_id=str(uuid4()),
            project_name=context.project_name,
            overall_status=overall_status,
            total_items=total_items,
            fatal_count=fatal_count,
            major_count=major_count,
            warning_count=warning_count,
            info_count=info_count,
            pass_rate=pass_rate,
            sections=context.sections,
            summaries=context.summaries,
            compliance_findings=context.compliance_findings,
            arithmetic_errors=context.arithmetic_errors,
            cost_indices=context.cost_indices,
            issues=issues,
            recommendations=self._build_recommendations(issues, context),
            total_rt=context.total_rt,
            building_area=context.building_area,
        )

        report.markdown = self._render_professional_markdown(report, context)
        context.report = report
        return context, report

    def _build_issues(self, alerts: List[Dict]) -> List[AuditIssue]:
        issues: List[AuditIssue] = []
        for idx, alert in enumerate(alerts, start=1):
            severity = alert.get("severity", "warning")
            category = self._category_for(alert.get("type", ""))
            location = str(alert.get("item", ""))
            issues.append(
                AuditIssue(
                    issue_id=f"ISSUE-{idx:04d}",
                    severity=severity,
                    category=category,
                    location=location,
                    message=alert.get("message", ""),
                    suggestion=alert.get("suggestion", ""),
                    expected=alert.get("expected"),
                    actual=alert.get("actual"),
                )
            )
        return issues

    def _category_for(self, alert_type: str) -> str:
        if "算术" in alert_type or "计算" in alert_type:
            return "arithmetic"
        if "价格" in alert_type or "历史" in alert_type or "报价" in alert_type:
            return "price_comparison"
        if "合规" in alert_type:
            return "compliance"
        if "造价" in alert_type or "占比" in alert_type:
            return "cost_anomaly"
        return "data_quality"

    def _determine_status(self, fatal_count: int, major_count: int) -> str:
        if fatal_count > 0:
            return "fail"
        if major_count > 10:
            return "conditional_pass"
        if major_count > 0:
            return "conditional_pass"
        return "pass"

    def _build_recommendations(self, issues: List[AuditIssue], context: PipelineContext) -> List[Dict]:
        recs: List[Dict] = []

        # 计算问题建议
        arithmetic_issues = [i for i in issues if i.category == "arithmetic"]
        if arithmetic_issues:
            recs.append({
                "category": "计算准确性",
                "priority": "高",
                "action": f"发现 {len(arithmetic_issues)} 项算术计算错误，需按'工程量×单价'重新核算并修正合价",
                "detail": f"涉及金额差异: {sum(abs(i.actual - i.expected) for i in arithmetic_issues if i.expected and i.actual):.2f} 元"
            })

        # 价格异常建议
        price_issues = [i for i in issues if i.category == "price_comparison"]
        if price_issues:
            recs.append({
                "category": "价格合理性",
                "priority": "高",
                "action": f"发现 {len(price_issues)} 项价格偏离历史基准超过20%，需核查报价依据",
                "detail": "建议调取历史合同或市场询价单进行对比"
            })

        # 合规问题建议
        compliance_issues = [i for i in issues if i.category == "compliance"]
        if compliance_issues:
            recs.append({
                "category": "规范合规",
                "priority": "中",
                "action": f"发现 {len(compliance_issues)} 项不符合GB 50500规范，需补充项目特征或修正计量单位",
                "detail": "重点检查设备类项目的规格描述是否完整"
            })

        # 造价占比建议
        cost_issues = [i for i in issues if i.category == "cost_anomaly"]
        if cost_issues:
            recs.append({
                "category": "造价合理性",
                "priority": "中",
                "action": f"发现 {len(cost_issues)} 项费用占比异常，建议核查甲供设备标记和人工费计取",
                "detail": "材料费占比应在50%-85%之间，人工费占比应在5%-50%之间"
            })

        return recs

    def _render_professional_markdown(self, report: QuoteAuditReport, context: PipelineContext) -> str:
        """生成专业报价审核报告"""
        lines = []

        # ========== 报告封面 ==========
        lines.extend([
            "# 📋 报价审核报告",
            "",
            f"**项目名称**: {report.project_name}",
            f"**审核时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**报告编号**: {report.report_id[:8].upper()}",
            "",
            "---",
            ""
        ])

        # ========== 执行摘要 ==========
        lines.extend(self._render_executive_summary(report))

        # ========== 费用构成分析 ==========
        lines.extend(self._render_cost_structure(report, context))

        # ========== 算术校验详情 ==========
        lines.extend(self._render_arithmetic_details(report))

        # ========== 价格偏离分析 ==========
        lines.extend(self._render_price_analysis(report, context))

        # ========== 分部工程明细 ==========
        lines.extend(self._render_section_details(report))

        # ========== 问题清单 ==========
        lines.extend(self._render_issues_list(report))

        # ========== 优化建议 ==========
        lines.extend(self._render_recommendations(report))

        # ========== 附录 ==========
        lines.extend(self._render_appendix(report))

        return "\n".join(lines)

    def _render_executive_summary(self, report: QuoteAuditReport) -> List[str]:
        """执行摘要"""
        status_emoji = {"pass": "✅", "conditional_pass": "⚠️", "fail": "❌"}
        status_text = {"pass": "通过", "conditional_pass": "有条件通过", "fail": "不通过"}
        status_color = {"pass": "🟢", "conditional_pass": "🟡", "fail": "🔴"}

        lines = [
            "## 📊 执行摘要",
            "",
            "| 指标 | 数值 |",
            "|------|------|",
            f"| 审核结论 | {status_color.get(report.overall_status, '')} **{status_text.get(report.overall_status, report.overall_status)}** |",
            f"| 清单条目 | {report.total_items} 项 |",
            f"| 通过率 | {float(report.pass_rate) * 100:.1f}% |",
            f"| 致命错误 | {report.fatal_count} 项 |",
            f"| 重大偏差 | {report.major_count} 项 |",
            f"| 警告提示 | {report.warning_count} 项 |",
            "",
        ]

        # 问题分类统计
        if report.issues:
            by_category = {}
            for issue in report.issues:
                cat = issue.category
                by_category[cat] = by_category.get(cat, 0) + 1

            lines.append("**问题分类统计:**")
            cat_names = {
                "arithmetic": "算术计算错误",
                "price_comparison": "价格偏离异常",
                "compliance": "规范合规问题",
                "cost_anomaly": "造价占比异常",
                "data_quality": "数据质量问题"
            }
            for cat, count in sorted(by_category.items(), key=lambda x: -x[1]):
                lines.append(f"- {cat_names.get(cat, cat)}: **{count}** 项")
            lines.append("")

        return lines

    def _render_cost_structure(self, report: QuoteAuditReport, context: PipelineContext) -> List[str]:
        """费用构成分析"""
        lines = ["## 💰 费用构成分析", ""]

        if not report.summaries:
            lines.append("*暂无费用汇总数据*")
            lines.append("")
            return lines

        for summary in report.summaries:
            phase = summary.phase or "未知"
            grand_total = float(summary.grand_total) if summary.grand_total else 0

            lines.append(f"### {phase}费用汇总")
            lines.append("")

            if grand_total > 0:
                mat_amt = float(summary.subtotal_material) if summary.subtotal_material else 0
                lab_amt = float(summary.subtotal_labor) if summary.subtotal_labor else 0
                measures = float(summary.measures_cost) if summary.measures_cost else 0
                tax = float(summary.tax) if summary.tax else 0

                mat_ratio = mat_amt / grand_total * 100
                lab_ratio = lab_amt / grand_total * 100
                measures_ratio = measures / grand_total * 100
                tax_ratio = tax / grand_total * 100

                lines.extend([
                    f"| 费用项目 | 金额(元) | 占比 |",
                    f"|----------|----------|------|",
                    f"| 材料费 | {mat_amt:,.2f} | {mat_ratio:.1f}% |",
                    f"| 人工费 | {lab_amt:,.2f} | {lab_ratio:.1f}% |",
                    f"| 措施费(3%) | {measures:,.2f} | {measures_ratio:.1f}% |",
                    f"| 税金(9%) | {tax:,.2f} | {tax_ratio:.1f}% |",
                    f"| **{'合计' if phase == '一期' else phase}** | **{grand_total:,.2f}** | **100%** |",
                    ""
                ])

                # 指标判断
                if mat_ratio < 50:
                    lines.append(f"⚠️ **警告**: 材料费占比({mat_ratio:.1f}%)偏低，可能存在甲供设备未计入或人工费虚高")
                elif mat_ratio > 85:
                    lines.append(f"⚠️ **警告**: 材料费占比({mat_ratio:.1f}%)偏高，建议核查人工费是否漏计")
                else:
                    lines.append(f"✅ 材料费占比({mat_ratio:.1f}%)处于合理区间(50%-85%)")

                if lab_ratio < 5:
                    lines.append(f"⚠️ **警告**: 人工费占比({lab_ratio:.1f}%)偏低，核查人工费是否漏计")
                elif lab_ratio > 50:
                    lines.append(f"⚠️ **警告**: 人工费占比({lab_ratio:.1f}%)偏高，建议核查")
                else:
                    lines.append(f"✅ 人工费占比({lab_ratio:.1f}%)处于合理区间(5%-50%)")
                lines.append("")

        # 单位造价指标
        if context.total_rt or context.building_area:
            lines.append("### 📐 单位造价指标")
            lines.append("")
            for summary in report.summaries:
                if summary.grand_total and summary.grand_total > 0:
                    phase = summary.phase or "未知"
                    total = float(summary.grand_total)
                    if context.total_rt:
                        lines.append(f"- {phase} **元/RT**: {total / float(context.total_rt):,.2f} 元/RT")
                    if context.building_area:
                        lines.append(f"- {phase} **元/㎡**: {total / float(context.building_area):,.2f} 元/㎡")
            lines.append("")

        return lines

    def _render_arithmetic_details(self, report: QuoteAuditReport) -> List[str]:
        """算术校验详情"""
        lines = ["## 🧮 算术校验详情", ""]

        if not report.arithmetic_errors:
            lines.append("✅ **所有算术校验通过，未发现计算错误**")
            lines.append("")
            return lines

        # 按错误类型分组
        by_type = {}
        for err in report.arithmetic_errors:
            t = err.error_type
            by_type.setdefault(t, []).append(err)

        type_names = {
            "material_mismatch": "主材合价计算错误",
            "labor_mismatch": "人工合价计算错误",
            "subtotal_mismatch": "分部小计汇总错误",
            "fee_mismatch": "费用计算错误"
        }

        total_diff = Decimal("0")

        for err_type, errors in by_type.items():
            lines.append(f"### {type_names.get(err_type, err_type)} ({len(errors)}项)")
            lines.append("")
            lines.append("| 序号 | 项目名称 | 期望值 | 实际值 | 差异 | 严重程度 |")
            lines.append("|------|----------|--------|--------|------|----------|")

            for err in errors:
                seq = err.item_sequence or "-"
                name = err.item_name[:30] + "..." if len(err.item_name) > 30 else err.item_name
                expected = float(err.expected) if err.expected else 0
                actual = float(err.actual) if err.actual else 0
                diff = actual - expected
                total_diff += abs(err.difference) if err.difference else Decimal("0")

                diff_str = f"{diff:+,.2f}"
                severity_badge = {"fatal": "🔴", "major": "🟡", "warning": "🟢"}.get(err.severity, "")
                lines.append(f"| {seq} | {name} | {expected:,.2f} | {actual:,.2f} | {diff_str} | {severity_badge} {err.severity} |")

            lines.append("")

        lines.append(f"**差异总额**: {float(total_diff):,.2f} 元")
        lines.append("")
        lines.append("> 💡 **建议**: 按'工程量×单价'重新核算，修正所有合价错误后重新汇总")
        lines.append("")

        return lines

    def _render_price_analysis(self, report: QuoteAuditReport, context: PipelineContext) -> List[str]:
        """价格偏离分析"""
        lines = ["## 📈 历史价格对比分析", ""]

        # 获取价格相关问题
        price_issues = [i for i in report.issues if i.category == "price_comparison"]
        price_comparisons = getattr(context, 'price_comparisons', [])

        if not price_comparisons and not price_issues:
            lines.append("✅ **价格分析通过，未发现明显偏离历史基准的价格异常**")
            lines.append("")
            return lines

        if price_comparisons:
            # 按严重程度分组
            by_severity = {"fatal": [], "major": [], "warning": [], "info": []}
            for pc in price_comparisons:
                if pc.severity in by_severity:
                    by_severity[pc.severity].append(pc)

            severity_names = {
                "fatal": "🔴 严重偏离 (>50%)",
                "major": "🟠 较大偏离 (30%-50%)",
                "warning": "🟡 轻度偏离 (20%-30%)",
                "info": "ℹ️ 正常范围 (<20%)"
            }

            lines.append(f"### 设备价格对比详情 ({len(price_comparisons)}项设备已对比)")
            lines.append("")

            for severity in ["fatal", "major", "warning", "info"]:
                comparisons = by_severity.get(severity, [])
                if not comparisons:
                    continue

                lines.append(f"#### {severity_names.get(severity, severity)} ({len(comparisons)}项)")
                lines.append("")
                lines.append("| 设备名称 | 当前报价 | 历史均价 | 偏离幅度 | 合同日期 |")
                lines.append("|----------|----------|----------|----------|----------|")

                for pc in comparisons[:15]:  # 最多显示15项
                    dev_str = f"{pc.deviation_percent:+.1f}%" if pc.deviation_percent else "N/A"
                    hist_date = pc.historical_prices[0].contract_date if pc.historical_prices else "N/A"
                    current_str = f"{float(pc.current_price):,.2f}"
                    hist_str = f"{float(pc.historical_avg_price):,.2f}" if pc.historical_avg_price else "N/A"
                    lines.append(f"| {pc.item_name[:20]}... | {current_str} | {hist_str} | {dev_str} | {hist_date} |")

                lines.append("")

                if len(comparisons) > 15:
                    lines.append(f"_...还有 {len(comparisons) - 15} 项未显示_")
                    lines.append("")

        elif price_issues:
            lines.append(f"发现 **{len(price_issues)}** 项价格可能偏离正常范围:")
            lines.append("")

            for issue in price_issues[:20]:
                lines.append(f"- **{issue.location}**: {issue.message}")
                if issue.suggestion:
                    lines.append(f"  - 建议: {issue.suggestion}")
            lines.append("")

            if len(price_issues) > 20:
                lines.append(f"_...还有 {len(price_issues) - 20} 项价格异常未显示_")
                lines.append("")

        lines.append("> 💡 **建议**: 调取历史合同或市场询价单，对偏离超过20%的项目进行重点复核")
        lines.append("")

        return lines

    def _render_section_details(self, report: QuoteAuditReport) -> List[str]:
        """分部工程明细"""
        lines = ["## 📑 分部工程明细", ""]

        if not report.sections:
            lines.append("*暂无分部工程数据*")
            lines.append("")
            return lines

        for section in report.sections:
            sec_name = section.section_name or section.section_id or "未知分部"
            lines.append(f"### {sec_name}")
            lines.append("")

            # 统计
            items_in_section = [i for i in report.issues if section.section_name and i.location and section.section_name in i.location]
            error_count = len([i for i in items_in_section if i.severity in ("fatal", "major")])

            lines.extend([
                f"- 条目数量: {len(section.items) if section.items else 0}",
                f"- 材料小计: {float(section.subtotal_material):,.2f} 元" if section.subtotal_material else "",
                f"- 人工小计: {float(section.subtotal_labor):,.2f} 元" if section.subtotal_labor else "",
                f"- 异常问题: {error_count} 项" if error_count > 0 else "- 无异常",
                ""
            ])

        return lines

    def _render_issues_list(self, report: QuoteAuditReport) -> List[str]:
        """问题清单"""
        lines = ["## ⚠️ 问题清单", ""]

        if not report.issues:
            lines.append("✅ **未发现问题清单条目**")
            lines.append("")
            return lines

        # 按严重程度分组
        by_severity = {"fatal": [], "major": [], "warning": [], "info": []}
        for issue in report.issues:
            sev = issue.severity
            if sev in by_severity:
                by_severity[sev].append(issue)

        severity_names = {"fatal": "🔴 致命错误", "major": "🟠 重大偏差", "warning": "🟡 警告提示", "info": "ℹ️ 提示信息"}
        category_names = {
            "arithmetic": "算术计算",
            "price_comparison": "价格偏离",
            "compliance": "规范合规",
            "cost_anomaly": "造价异常",
            "data_quality": "数据质量"
        }

        for severity in ["fatal", "major", "warning", "info"]:
            issues = by_severity.get(severity, [])
            if not issues:
                continue

            lines.append(f"### {severity_names.get(severity, severity)} ({len(issues)}项)")
            lines.append("")

            for issue in issues[:30]:
                cat = category_names.get(issue.category, issue.category)
                lines.append(f"**[{issue.issue_id}]** {issue.location}")
                lines.append(f"- 类别: {cat}")
                lines.append(f"- 问题: {issue.message}")
                if issue.expected is not None and issue.actual is not None:
                    lines.append(f"- 期望值: {issue.expected}, 实际值: {issue.actual}")
                if issue.suggestion:
                    lines.append(f"- 建议: {issue.suggestion}")
                lines.append("")

            if len(issues) > 30:
                lines.append(f"_...还有 {len(issues) - 30} 项未显示_")
                lines.append("")

        return lines

    def _render_recommendations(self, report: QuoteAuditReport) -> List[str]:
        """优化建议"""
        lines = ["## 💡 优化建议", ""]

        if not report.recommendations:
            lines.append("✅ **暂无优化建议**")
            lines.append("")
            return lines

        for idx, rec in enumerate(report.recommendations, start=1):
            priority_emoji = {"高": "🔴", "中": "🟡", "低": "🟢"}.get(rec.get("priority", ""), "")
            lines.append(f"### {priority_emoji} {rec.get('category', '建议')} (优先级: {rec.get('priority', '中')})")
            lines.append("")
            lines.append(f"**问题**: {rec.get('action', '待明确')}")
            if rec.get("detail"):
                lines.append(f"**详情**: {rec['detail']}")
            lines.append("")

        return lines

    def _render_appendix(self, report: QuoteAuditReport) -> List[str]:
        """附录"""
        lines = [
            "---",
            "",
            "## 📎 附录",
            "",
            f"- 报告编号: `{report.report_id}`",
            f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- 数据来源: {report.project_name}",
        ]

        if report.total_rt:
            lines.append(f"- 项目制冷量: {report.total_rt} RT")
        if report.building_area:
            lines.append(f"- 建筑面积: {report.building_area} ㎡")

        lines.extend([
            "",
            "---",
            "*本报告由 Agentic RAG 系统自动生成，仅供参考，最终以人工复核为准。*",
            ""
        ])

        return lines
