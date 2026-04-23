"""
Stage 3: 核对引擎层 (Compliance Engine)

负责：
1. Hard Check: 数值硬规则核对（Python计算）
2. Soft Check: 语义评估核对（LLM辅助）
3. KB Verify: 知识库校验（Qdrant查询）

输出每条条款的三层核对结果
"""

import logging
import json
from typing import List, Dict, Any, Optional, Callable, Union
from dataclasses import dataclass

from .models import (
    TenderChecklist,
    BidResponse,
    ComplianceResult,
    ComplianceCheck,
    HardCheckResult,
    SoftCheckResult,
    KBVerifyResult,
    TenderItem,
    MetricSpec,
    EquipmentRow,
    ComplianceStatus,
    DeviationType,
    RiskLevel,
)
from .config import COMPLIANCE_ENGINE_CONFIG

logger = logging.getLogger(__name__)


class HardCheckEngine:
    """
    Hard Check: 数值硬规则引擎

    纯Python计算，无LLM参与，确保可审计性
    """

    OPERATORS: Dict[str, Callable] = {
        ">=": lambda x, y: x >= y,
        "<=": lambda x, y: x <= y,
        ">": lambda x, y: x > y,
        "<": lambda x, y: x < y,
        "==": lambda x, y: x == y,
        "in_range": lambda x, y: y[0] <= x <= y[1] if isinstance(y, (list, tuple)) and len(y) == 2 else False,
        "in_list": lambda x, y: x in y if isinstance(y, (list, tuple)) else False,
    }

    def check(self, tender_item: TenderItem, bid_response: Dict[str, Any]) -> HardCheckResult:
        """
        执行Hard Check核对

        Args:
            tender_item: 招标条款项
            bid_response: 投标响应数据

        Returns:
            HardCheckResult: 硬核对结果
        """
        # 如果没有量化指标，无法进行Hard Check
        if not tender_item.quantifiable or not tender_item.metric:
            return HardCheckResult(
                status="未响应",
                deviation_type="未响应",
                bid_value=None,
                target_value=None,
                risk_level="高",
                action="无法进行数值核对，需人工审核",
            )

        metric = tender_item.metric

        # 从投标响应中提取对应值
        bid_value = self._extract_bid_value(
            tender_item, bid_response, metric.parameter
        )

        if bid_value is None:
            return HardCheckResult(
                status="未响应",
                deviation_type="未响应",
                bid_value=None,
                target_value=metric.target_value,
                operator=metric.operator,
                risk_level="高" if tender_item.penalty_type == "废标" else "中",
                penalty_type=tender_item.penalty_type,
                action="强制人工审核" if tender_item.penalty_type == "废标" else "需处理",
            )

        # 执行比较
        try:
            operator_func = self.OPERATORS.get(metric.operator)
            if not operator_func:
                logger.warning(f"未知的操作符: {metric.operator}")
                is_compliant = False
            else:
                is_compliant = operator_func(bid_value, metric.target_value)

        except Exception as e:
            logger.error(f"数值比较失败: {e}")
            is_compliant = False

        # 计算偏离幅度
        margin = None
        margin_percent = None
        if isinstance(bid_value, (int, float)) and isinstance(metric.target_value, (int, float)):
            margin = bid_value - metric.target_value
            if metric.target_value != 0:
                margin_percent = (margin / metric.target_value) * 100

        # 判定偏离类型
        if is_compliant:
            if margin is not None and margin > 0:
                deviation_type = "正偏离"  # 优于要求
            else:
                deviation_type = "符合"
        else:
            deviation_type = "负偏离" if margin is not None and margin < 0 else "不符合"

        # 风险等级
        if tender_item.penalty_type == "废标" and not is_compliant:
            risk_level = "极高"
        elif not is_compliant:
            risk_level = "高"
        elif deviation_type == "正偏离":
            risk_level = "低"
        else:
            risk_level = "无"

        return HardCheckResult(
            status="符合" if is_compliant else "不符合",
            deviation_type=deviation_type,
            bid_value=bid_value,
            target_value=metric.target_value,
            operator=metric.operator,
            margin=margin,
            margin_percent=margin_percent,
            unit=metric.unit,
            risk_level=risk_level,
            penalty_type=tender_item.penalty_type,
            action="通过" if is_compliant else "需处理",
        )

    def _extract_bid_value(
        self,
        tender_item: TenderItem,
        bid_response: Dict[str, Any],
        parameter: str,
    ) -> Optional[Any]:
        """
        从投标响应中提取指定参数的值

        简化实现，实际需要更复杂的映射逻辑
        """
        # 从设备参数表中查找
        equipment_tables = bid_response.get("equipment_tables", [])

        for table in equipment_tables:
            rows = table.get("rows", [])
            for row in rows:
                params = row.get("parameters", {})

                # 参数名映射
                param_mapping = {
                    "COP": ["COP", "cop"],
                    "IPLV": ["IPLV", "iplv"],
                    "制冷量": ["制冷量_kW", "制冷量", "制冷量(kW)"],
                    "输入功率": ["输入功率_kW", "输入功率", "功率"],
                }

                possible_keys = param_mapping.get(parameter, [parameter])
                for key in possible_keys:
                    if key in params:
                        return params[key]

        return None


class SoftCheckEngine:
    """
    Soft Check: 语义评估引擎

    使用LLM进行语义评估
    """

    def __init__(
        self,
        llm_model: str = "qwen-max",
        confidence_threshold: float = 0.7,
    ):
        self.llm_model = llm_model
        self.confidence_threshold = confidence_threshold

    def check(
        self,
        tender_item: TenderItem,
        bid_response: Dict[str, Any],
    ) -> SoftCheckResult:
        """
        执行Soft Check语义评估

        使用LLM进行语义相似度和响应质量评估
        """
        import json
        from langchain_core.messages import HumanMessage, SystemMessage

        try:
            # 尝试导入LLM
            from langchain_rag.llm.qwen import get_qwen_chat
        except ImportError:
            logger.warning("LLM module not available, returning placeholder result")
            return SoftCheckResult(
                is_responded="未响应",
                response_quality="待评估",
                suggested_score=0,
                max_score=tender_item.score_weight,
                confidence=0.0,
                reasoning="LLM模块不可用",
                evidence="",
                needs_manual_review=True,
            )

        # 从bid_response中提取相关内容
        bid_content = self._extract_relevant_content(tender_item, bid_response)

        if not bid_content:
            return SoftCheckResult(
                is_responded="未响应",
                response_quality="差",
                suggested_score=0,
                max_score=tender_item.score_weight,
                confidence=0.9,
                reasoning="投标文件中未找到对此条款的响应",
                evidence="",
                needs_manual_review=True,
            )

        # 构建LLM提示词
        system_prompt = """你是一个专业的标书审核专家。请评估投标响应与招标条款的匹配程度。

请按以下JSON格式输出评估结果：
{
    "is_responded": "已响应|未响应|部分响应",
    "response_quality": "优|良|中|差",
    "suggested_score": 0-100,
    "confidence": 0.0-1.0,
    "reasoning": "评估理由",
    "evidence": "关键证据引用"
}

评分标准：
- 优：完全响应，内容详实，超出预期
- 良：完整响应，内容充分
- 中：基本响应，内容有欠缺
- 差：响应不充分或有重大遗漏
"""

        user_prompt = f"""招标条款：
编号：{tender_item.sequence}
内容：{tender_item.content}
类型：{tender_item.type}

投标响应：
{bid_content}

请评估该投标响应的质量。"""

        try:
            llm = get_qwen_chat(
                model_name=self.llm_model,
                temperature=0.1,
                max_tokens=500,
            )

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            response = llm.invoke(messages)
            result_text = response.content.strip()

            # 尝试解析JSON
            try:
                # 清理响应（可能包裹在```json ```中）
                if result_text.startswith("```json"):
                    result_text = result_text[7:]
                if result_text.startswith("```"):
                    result_text = result_text[3:]
                if result_text.endswith("```"):
                    result_text = result_text[:-3]

                result_json = json.loads(result_text.strip())

                return SoftCheckResult(
                    is_responded=result_json.get("is_responded", "待评估"),
                    response_quality=result_json.get("response_quality", "待评估"),
                    suggested_score=result_json.get("suggested_score", 0),
                    max_score=tender_item.score_weight,
                    confidence=result_json.get("confidence", 0.5),
                    reasoning=result_json.get("reasoning", ""),
                    evidence=result_json.get("evidence", ""),
                    needs_manual_review=result_json.get("confidence", 0) < self.confidence_threshold,
                )
            except json.JSONDecodeError:
                # JSON解析失败，返回简单评估
                return SoftCheckResult(
                    is_responded="已响应",
                    response_quality="中",
                    suggested_score=tender_item.score_weight * 0.5,
                    max_score=tender_item.score_weight,
                    confidence=0.5,
                    reasoning="LLM响应格式异常，需人工审核",
                    evidence=result_text[:200],
                    needs_manual_review=True,
                )

        except Exception as e:
            logger.error(f"Soft Check LLM call failed: {e}")
            return SoftCheckResult(
                is_responded="待评估",
                response_quality="待评估",
                suggested_score=0,
                max_score=tender_item.score_weight,
                confidence=0.0,
                reasoning=f"LLM调用失败: {str(e)}",
                evidence="",
                needs_manual_review=True,
            )

    def _extract_relevant_content(self, tender_item: TenderItem, bid_response: Dict[str, Any]) -> str:
        """从投标响应中提取与招标条款相关的内容"""
        relevant_parts = []

        # 从技术方案中查找
        technical_proposal = bid_response.get("technical_proposal", {})
        for section, content in technical_proposal.items():
            if any(kw in str(content) for kw in tender_item.keywords):
                relevant_parts.append(f"[{section}]\n{content}")

        # 从设备参数表中查找
        equipment_tables = bid_response.get("equipment_tables", [])
        for table in equipment_tables:
            rows = table.get("rows", [])
            for row in rows:
                params = row.get("parameters", {})
                param_str = json.dumps(params, ensure_ascii=False)
                if any(kw in param_str for kw in tender_item.keywords):
                    relevant_parts.append(f"[设备表: {table.get('name', '未知')}]\n{param_str}")

        return "\n\n".join(relevant_parts) if relevant_parts else ""


class KBVerifyEngine:
    """
    KB Verify: 知识库校验引擎

    使用Qdrant查询验证厂家参数
    """

    def __init__(
        self,
        qdrant_host: Optional[str] = None,
        collection: str = "hvac_equipment",
        deviation_threshold: float = 10.0,
    ):
        self.qdrant_host = qdrant_host
        self.collection = collection
        self.deviation_threshold = deviation_threshold

    def verify(
        self,
        tender_item: TenderItem,
        bid_response: Dict[str, Any],
    ) -> KBVerifyResult:
        """
        执行KB知识库校验

        使用Qdrant查询验证厂家参数的真实性
        """
        parameter_alerts = []
        kb_value = None
        bid_value = None
        deviation_percent = None
        model_found = False
        kb_matched = False

        # 如果没有量化指标，无需KB校验
        if not tender_item.quantifiable or not tender_item.metric:
            return KBVerifyResult(
                kb_matched=False,
                model_found=False,
                parameter_alerts=["无非标参数需要校验"],
                kb_value=None,
                bid_value=None,
                deviation_percent=None,
            )

        try:
            # 尝试导入Qdrant
            from langchain_rag.vectorstore.qdrant import get_qdrant_vectorstore
        except ImportError:
            logger.warning("Qdrant module not available, returning placeholder result")
            return KBVerifyResult(
                kb_matched=False,
                model_found=False,
                parameter_alerts=["知识库模块不可用"],
                kb_value=None,
                bid_value=None,
                deviation_percent=None,
            )

        metric = tender_item.metric
        param_name = metric.parameter

        # 从投标响应中提取设备型号和参数值
        bid_model, bid_val = self._extract_model_and_value(
            tender_item, bid_response, param_name
        )

        if not bid_model:
            return KBVerifyResult(
                kb_matched=False,
                model_found=False,
                parameter_alerts=["未找到设备型号，无法进行KB校验"],
                kb_value=None,
                bid_value=bid_val,
                deviation_percent=None,
            )

        bid_value = bid_val

        try:
            # 查询Qdrant知识库
            vectorstore = get_qdrant_vectorstore(
                collection_name=self.collection,
                qdrant_host=self.qdrant_host,
            )

            # 搜索相关设备
            query_text = f"设备型号 {bid_model} {param_name}"
            docs = vectorstore.similarity_search(query_text, k=3)

            if not docs:
                parameter_alerts.append(f"知识库中未找到型号 {bid_model}")
                return KBVerifyResult(
                    kb_matched=True,
                    model_found=False,
                    parameter_alerts=parameter_alerts,
                    kb_value=None,
                    bid_value=bid_value,
                    deviation_percent=None,
                )

            model_found = True
            kb_matched = True

            # 从检索结果中提取参数值
            kb_val = self._extract_param_from_docs(docs, param_name)

            if kb_val is None:
                parameter_alerts.append(f"知识库中找到型号 {bid_model}，但未找到{param_name}参数")
                return KBVerifyResult(
                    kb_matched=True,
                    model_found=True,
                    parameter_alerts=parameter_alerts,
                    kb_value=None,
                    bid_value=bid_value,
                    deviation_percent=None,
                )

            kb_value = kb_val

            # 计算偏离百分比
            if isinstance(kb_val, (int, float)) and isinstance(bid_val, (int, float)) and kb_val != 0:
                deviation_percent = abs((bid_val - kb_val) / kb_val) * 100

                if deviation_percent > self.deviation_threshold:
                    parameter_alerts.append(
                        f"{param_name}参数偏离知识库 {deviation_percent:.1f}% "
                        f"(厂家标称: {kb_val}, 投标: {bid_val})"
                    )

            return KBVerifyResult(
                kb_matched=kb_matched,
                model_found=model_found,
                parameter_alerts=parameter_alerts,
                kb_value=kb_value,
                bid_value=bid_value,
                deviation_percent=deviation_percent,
            )

        except Exception as e:
            logger.error(f"KB Verify Qdrant query failed: {e}")
            parameter_alerts.append(f"知识库查询失败: {str(e)}")
            return KBVerifyResult(
                kb_matched=False,
                model_found=False,
                parameter_alerts=parameter_alerts,
                kb_value=None,
                bid_value=bid_value,
                deviation_percent=None,
            )

    def _extract_model_and_value(
        self,
        tender_item: TenderItem,
        bid_response: Dict[str, Any],
        param_name: str,
    ) -> tuple[Optional[str], Optional[Any]]:
        """从投标响应中提取设备型号和参数值"""
        equipment_tables = bid_response.get("equipment_tables", [])

        for table in equipment_tables:
            rows = table.get("rows", [])
            for row in rows:
                model = row.get("model")
                params = row.get("parameters", {})

                # 查找参数值
                param_mapping = {
                    "COP": ["COP", "cop"],
                    "IPLV": ["IPLV", "iplv"],
                    "制冷量": ["制冷量_kW", "制冷量", "制冷量(kW)"],
                    "输入功率": ["输入功率_kW", "输入功率", "功率"],
                }

                possible_keys = param_mapping.get(param_name, [param_name])
                param_val = None
                for key in possible_keys:
                    if key in params:
                        param_val = params[key]
                        break

                if model and param_val is not None:
                    return model, param_val

        return None, None

    def _extract_param_from_docs(self, docs, param_name: str) -> Optional[Any]:
        """从检索文档中提取参数值"""
        for doc in docs:
            content = doc.page_content
            metadata = doc.metadata or {}

            # 先尝试从metadata获取
            if param_name in metadata:
                val = metadata[param_name]
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return val

            # 尝试从content中解析
            import re
            patterns = [
                rf"{param_name}[：:]\s*([\d.]+)",
                rf"{param_name}\s*=\s*([\d.]+)",
            ]
            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    try:
                        return float(match.group(1))
                    except (ValueError, TypeError):
                        pass

        return None


class Stage3Compliance:
    """
    Stage 3: 核对引擎层主类

    整合Hard Check、Soft Check、KB Verify三层核对
    """

    def __init__(
        self,
        llm_model: str = "qwen-max",
        qdrant_host: Optional[str] = None,
        enable_kb_verify: bool = True,
    ):
        self.hard_engine = HardCheckEngine()
        self.soft_engine = SoftCheckEngine(llm_model=llm_model)

        if enable_kb_verify and qdrant_host:
            self.kb_engine = KBVerifyEngine(qdrant_host=qdrant_host)
        else:
            self.kb_engine = None

    def check(
        self,
        checklist: TenderChecklist,
        bid_response: BidResponse,
    ) -> ComplianceResult:
        """
        执行三层核对

        Args:
            checklist: 招标书Checklist
            bid_response: 投标书响应

        Returns:
            ComplianceResult: 核对结果
        """
        import time
        start_time = time.time()

        logger.info(f"[Stage 3] 开始三层核对")
        logger.info(f"  条款总数: {len(checklist.items)}条")
        logger.info(f"  设备表数: {len(bid_response.equipment_tables)}个")
        logger.info(f"  KB Verify: {'启用' if self.kb_engine else '禁用'}")

        checks = []
        hard_count = 0
        soft_count = 0
        kb_count = 0
        hard_passed = 0
        hard_failed = 0

        for idx, item in enumerate(checklist.items):
            if idx % 10 == 0:
                logger.debug(f"  处理进度: {idx}/{len(checklist.items)} ({idx/len(checklist.items)*100:.0f}%)")

            check = ComplianceCheck(
                item_id=item.item_id,
                check_type=self._determine_check_type(item),
            )

            # Hard Check: 量化指标
            if item.quantifiable and item.metric:
                logger.debug(f"    [Hard] {item.item_id}: {item.type} - {item.metric.parameter} {item.metric.operator} {item.metric.target_value}")
                hard_result = self.hard_engine.check(item, bid_response.dict())
                check.hard_result = hard_result
                check.final_status = hard_result.status
                check.final_risk_level = hard_result.risk_level
                hard_count += 1

                if hard_result.status == "符合":
                    hard_passed += 1
                    logger.debug(f"      ✓ 通过: 投标值{hard_result.bid_value} {hard_result.operator} 目标值{hard_result.target_value}")
                elif hard_result.status == "不符合":
                    hard_failed += 1
                    logger.warning(f"      ✗ 不通过: 投标值{hard_result.bid_value} {hard_result.operator} 目标值{hard_result.target_value} (风险:{hard_result.risk_level})")
                else:
                    logger.debug(f"      ? 待确认: {hard_result.status}")

            # Soft Check: 定性评估
            elif item.type == "评分项":
                logger.debug(f"    [Soft] {item.item_id}: {item.type} - {item.content[:50]}...")
                soft_result = self.soft_engine.check(item, bid_response.dict())
                check.soft_result = soft_result
                check.final_status = "待评估" if check.final_status is None else check.final_status
                soft_count += 1

                if soft_result.response_quality in ["优", "良"]:
                    logger.debug(f"      响应质量: {soft_result.response_quality}, 建议分: {soft_result.suggested_score}/{soft_result.max_score}")
                else:
                    logger.warning(f"      响应质量: {soft_result.response_quality}, 置信度: {soft_result.confidence:.2f}")

            # KB Verify: 知识库校验（可选）
            if self.kb_engine and item.quantifiable:
                logger.debug(f"    [KB] {item.item_id}: 验证{item.metric.parameter}")
                kb_result = self.kb_engine.verify(item, bid_response.dict())
                check.kb_result = kb_result
                kb_count += 1

                if kb_result.model_found:
                    if kb_result.deviation_percent:
                        if kb_result.deviation_percent > 10:
                            logger.warning(f"      ⚠ 参数偏离: {kb_result.deviation_percent:.1f}% (厂家:{kb_result.kb_value}, 投标:{kb_result.bid_value})")
                        else:
                            logger.debug(f"      ✓ 知识库验证通过: 偏离{kb_result.deviation_percent:.1f}%")
                    else:
                        logger.debug(f"      ✓ 知识库验证通过")
                else:
                    logger.debug(f"      知识库未找到该型号")

            checks.append(check)

        logger.info(f"  Hard Check: {hard_count}项 (通过:{hard_passed}, 不通过:{hard_failed})")
        logger.info(f"  Soft Check: {soft_count}项")
        logger.info(f"  KB Verify: {kb_count}项")

        # 生成汇总统计
        summary = self._generate_summary(checks)

        compliance_rate = summary.get("compliance_rate", 0)
        logger.info(f"  合规率: {compliance_rate:.1f}%")
        logger.info(f"  高风险项: {summary.get('risk_summary', {}).get('high_risk', 0)}项")
        logger.info(f"  中风险项: {summary.get('risk_summary', {}).get('medium_risk', 0)}项")

        total_elapsed = time.time() - start_time
        logger.info(f"[Stage 3] 核对完成, 总耗时{total_elapsed:.2f}秒")

        return ComplianceResult(
            tender_id=checklist.tender_id,
            bid_id=bid_response.bid_id,
            checks=checks,
            summary=summary,
        )

    def _determine_check_type(self, item: TenderItem) -> str:
        """确定核对类型"""
        if item.quantifiable:
            return "Hard"
        elif item.type == "评分项":
            return "Soft"
        else:
            return "Hard"  # 默认

    def _generate_summary(self, checks: List[ComplianceCheck]) -> Dict[str, Any]:
        """生成核对结果汇总"""
        total = len(checks)

        # Hard Check统计
        hard_checks = [c for c in checks if c.hard_result]
        hard_passed = sum(1 for c in hard_checks if c.hard_result.status == "符合")
        hard_failed = sum(1 for c in hard_checks if c.hard_result.status == "不符合")

        # 风险等级统计
        high_risk = sum(1 for c in checks if c.final_risk_level in ["高", "极高"])
        medium_risk = sum(1 for c in checks if c.final_risk_level == "中")

        return {
            "total_items": total,
            "hard_check": {
                "total": len(hard_checks),
                "passed": hard_passed,
                "failed": hard_failed,
                "not_checked": len(hard_checks) - hard_passed - hard_failed,
            },
            "risk_summary": {
                "high_risk": high_risk,
                "medium_risk": medium_risk,
                "low_risk": total - high_risk - medium_risk,
            },
            "compliance_rate": hard_passed / len(hard_checks) * 100 if hard_checks else 0,
        }
