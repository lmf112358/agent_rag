"""
Stage 2: 条款对齐层

负责：
1. 章节识别（基于规则+关键词+LLM辅助）
2. 条款提取（编号+内容+类型）
3. 投标响应提取（设备参数表、偏离表、技术方案）
4. 条款与响应对齐映射
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from pathlib import Path

from .models import (
    TenderDocument,
    BidDocument,
    TenderChecklist,
    TenderItem,
    MetricSpec,
    BidResponse,
    EquipmentTable,
    EquipmentRow,
    TechnicalSection,
    DeviationItem,
    QualificationDoc,
)
from .config import TENDER_SECTION_PATTERNS, EQUIPMENT_TABLE_PATTERNS

logger = logging.getLogger(__name__)


class Stage2Aligner:
    """
    Stage 2: 条款对齐层

    将招标书解析为结构化Checklist，
    将投标书解析为响应提取JSON，
    建立条款与响应的对齐映射。
    """

    def __init__(
        self,
        llm_model: str = "qwen-max",
        use_llm_for_section: bool = True,
    ):
        """
        初始化Stage2对齐器

        Args:
            llm_model: LLM模型名称
            use_llm_for_section: 是否使用LLM辅助章节识别
        """
        self.llm_model = llm_model
        self.use_llm_for_section = use_llm_for_section

    def align(
        self,
        tender_doc: TenderDocument,
        bid_doc: BidDocument,
    ) -> Tuple[TenderChecklist, BidResponse]:
        """
        执行条款对齐

        Args:
            tender_doc: 招标书文档对象
            bid_doc: 投标书文档对象

        Returns:
            Tuple[TenderChecklist, BidResponse]: 招标书Checklist和投标书响应
        """
        logger.info("[Stage 2] 开始条款对齐...")

        # 1. 解析招标书为Checklist
        logger.info("  解析招标书Checklist...")
        checklist = self._parse_tender_checklist(tender_doc)
        logger.info(f"    提取 {len(checklist.items)} 条条款")

        # 2. 解析投标书为响应提取
        logger.info("  解析投标书响应...")
        bid_response = self._parse_bid_response(bid_doc, checklist)
        logger.info(f"    提取 {len(bid_response.equipment_tables)} 个设备表")

        logger.info("[Stage 2] 条款对齐完成")
        return checklist, bid_response

    def _parse_tender_checklist(self, tender_doc: TenderDocument) -> TenderChecklist:
        """
        将招标书解析为结构化Checklist

        Args:
            tender_doc: 招标书文档对象

        Returns:
            TenderChecklist: 结构化Checklist
        """
        if not tender_doc.markdown:
            logger.warning("招标书Markdown为空")
            return TenderChecklist(
                tender_id=tender_doc.tender_id,
                project_name=tender_doc.project_name,
                project_type=tender_doc.project_type,
            )

        markdown = tender_doc.markdown

        # 1. 识别章节结构
        sections = self._identify_sections(markdown)

        # 2. 提取条款
        items = self._extract_items(markdown, sections)

        # 3. 计算统计信息
        statistics = {
            "total_items": len(items),
            "hard_requirements": sum(1 for i in items if i.type == "硬性指标"),
            "scoring_items": sum(1 for i in items if i.type == "评分项"),
            "qualification_items": sum(1 for i in items if i.type == "资质要求"),
            "business_items": sum(1 for i in items if i.type == "商务条款"),
        }

        return TenderChecklist(
            tender_id=tender_doc.tender_id,
            project_name=tender_doc.project_name,
            project_type=tender_doc.project_type,
            sections=sections,
            items=items,
            statistics=statistics,
        )

    def _identify_sections(self, markdown: str) -> List[Dict[str, Any]]:
        """
        识别文档章节结构

        使用规则+关键词匹配识别章节
        """
        sections = []
        lines = markdown.split('\n')

        for i, line in enumerate(lines):
            # 匹配各级标题
            if line.startswith('# '):
                # 一级标题
                title = line[2:].strip()
                section_type = self._classify_section(title)
                sections.append({
                    "section_id": f"S{len(sections)+1}",
                    "title": title,
                    "level": 1,
                    "line_num": i,
                    "type": section_type,
                })
            elif line.startswith('## '):
                # 二级标题
                title = line[3:].strip()
                section_type = self._classify_section(title)
                sections.append({
                    "section_id": f"S{len(sections)+1}",
                    "title": title,
                    "level": 2,
                    "line_num": i,
                    "type": section_type,
                })

        return sections

    def _classify_section(self, title: str) -> str:
        """
        根据标题内容分类章节类型
        """
        title_lower = title.lower()

        for section_type, config in TENDER_SECTION_PATTERNS.items():
            keywords = config.get("keywords", [])
            for kw in keywords:
                if kw.lower() in title_lower:
                    return section_type

        return "其他"

    def _extract_items(self, markdown: str, sections: List[Dict[str, Any]]) -> List[TenderItem]:
        """
        从文档中提取条款

        支持以下编号格式：
        - 数字编号：1.、2.、3.
        - 多级编号：1.1、1.2、2.1
        - 中文编号：一、二、三、
        - 括号编号：(1)、(2)、(3)
        """
        items = []
        lines = markdown.split('\n')

        # 条款编号正则模式
        item_patterns = [
            # 多级数字编号：1.1.1、2.1.2
            (r'^(\d+\.\d+(?:\.\d+)?)[\.、\s]+(.+)$', 'numbered'),
            # 一级数字编号：1.、2.
            (r'^(\d+)[\.、\s]+(.+)$', 'numbered'),
            # 中文编号：一、二、三
            (r'^([一二三四五六七八九十]+)[、\s]+(.+)$', 'chinese'),
            # 括号编号：(1)、(2)
            (r'^[（\(]([\d一二三四五六七八九十]+)[）\)][\.、\s]*(.+)$', 'bracket'),
        ]

        current_section_id = None

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # 更新当前章节
            for section in sections:
                if section.get("line_num") == i:
                    current_section_id = section.get("section_id")

            # 尝试匹配条款编号
            for pattern, pattern_type in item_patterns:
                import re
                match = re.match(pattern, line)
                if match:
                    sequence = match.group(1)
                    content = match.group(2).strip()

                    # 提取量化指标
                    metric = self._extract_metric(content)

                    # 判断条款类型
                    item_type = self._classify_item_type(content, current_section_id)

                    # 判断是否硬性指标
                    is_hard = self._is_hard_requirement(content)

                    item = TenderItem(
                        item_id=f"ITEM_{len(items)+1:03d}",
                        sequence=sequence,
                        section_id=current_section_id or "UNKNOWN",
                        type=item_type,
                        content=content,
                        quantifiable=metric is not None,
                        metric=metric,
                        keywords=self._extract_keywords(content),
                        penalty_type="废标" if is_hard else "扣分" if item_type == "评分项" else "无",
                        score_weight=self._estimate_score_weight(content, item_type),
                        confidence=0.8 if metric else 0.6,
                        needs_manual_check=metric is None and is_hard,
                    )
                    items.append(item)
                    break  # 匹配成功，跳出pattern循环

        return items

    def _extract_metric(self, content: str) -> Optional[MetricSpec]:
        """
        从条款内容中提取量化指标

        支持格式：
        - COP≥6.0
        - 制冷量≥1758kW
        - 交货期≤90天
        - 数量：2台
        """
        import re

        # 指标提取模式
        metric_patterns = [
            # COP≥6.0、COP>=6.0
            (r'COP\s*[≥>=]\s*(\d+\.?\d*)', 'COP', '>=', 'W/W'),
            # IPLV≥9.0
            (r'IPLV\s*[≥>=]\s*(\d+\.?\d*)', 'IPLV', '>=', 'W/W'),
            # 制冷量≥1758kW
            (r'制冷量\s*[≥>=]\s*(\d+\.?\d*)\s*k?W', '制冷量', '>=', 'kW'),
            # 输入功率≤300kW
            (r'输入功率\s*[≤<=]\s*(\d+\.?\d*)\s*k?W', '输入功率', '<=', 'kW'),
            # 交货期≤90天
            (r'交货期\s*[≤<=]\s*(\d+)\s*天', '交货期', '<=', '天'),
            # 质保期≥2年
            (r'质保期\s*[≥>=]\s*(\d+)\s*年', '质保期', '>=', '年'),
        ]

        for pattern, param, operator, unit in metric_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                return MetricSpec(
                    parameter=param,
                    operator=operator,
                    target_value=value,
                    unit=unit,
                )

        return None

    def _classify_item_type(self, content: str, section_id: Optional[str]) -> str:
        """判断条款类型"""
        content_lower = content.lower()

        # 硬性指标关键词
        hard_keywords = ["必须", "应满足", "不得低于", "至少", "最大", "最小", "不超过", "不低于"]
        for kw in hard_keywords:
            if kw in content:
                return "硬性指标"

        # 评分项关键词
        score_keywords = ["评分", "得分", "优", "良", "一般", "差", "档次"]
        for kw in score_keywords:
            if kw in content:
                return "评分项"

        # 资质要求
        if section_id and "资格" in str(section_id):
            return "资质要求"

        # 商务条款
        if section_id and "商务" in str(section_id):
            return "商务条款"

        return "其他"

    def _is_hard_requirement(self, content: str) -> bool:
        """判断是否硬性指标"""
        hard_keywords = ["必须", "应满足", "不得低于", "至少", "★", "※", "【必须】"]
        return any(kw in content for kw in hard_keywords)

    def _extract_keywords(self, content: str) -> List[str]:
        """提取关键词"""
        # 技术相关关键词
        tech_keywords = [
            "COP", "IPLV", "制冷量", "输入功率", "磁悬浮", "离心式", "螺杆式",
            "变频器", "群控", "能效", "节能", "AI", "预测性", "磁悬浮压缩机"
        ]

        found_keywords = []
        for kw in tech_keywords:
            if kw in content:
                found_keywords.append(kw)

        return found_keywords

    def _estimate_score_weight(self, content: str, item_type: str) -> float:
        """估算评分权重"""
        if item_type != "评分项":
            return 0.0

        # 从内容中提取分值
        import re
        score_match = re.search(r'(\d+)\s*分', content)
        if score_match:
            return float(score_match.group(1))

        # 默认分值
        return 1.0

    def _parse_bid_response(
        self,
        bid_doc: BidDocument,
        checklist: TenderChecklist,
    ) -> BidResponse:
        """
        解析投标书响应
        简化版本，实际实现需要更复杂的表格提取逻辑
        """
        # 简化实现，实际应该从Markdown中提取表格
        # 这里仅作为框架占位

        return BidResponse(
            bid_id=bid_doc.bid_id,
            tender_id=bid_doc.tender_id,
            project_name=bid_doc.company_name,
            equipment_tables=[],  # 实际应从Markdown提取
            deviation_table={},
            technical_proposal={},
            qualification_docs=[],
        )
