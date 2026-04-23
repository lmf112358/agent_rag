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
        import time
        start_time = time.time()

        logger.info(f"[Stage 2] 开始条款对齐")
        logger.info(f"  招标书ID: {tender_doc.tender_id}")
        logger.info(f"  投标书ID: {bid_doc.bid_id}")

        # 1. 解析招标书为Checklist
        logger.info(f"  [1/2] 解析招标书Checklist...")
        checklist_start = time.time()
        checklist = self._parse_tender_checklist(tender_doc)
        checklist_elapsed = time.time() - checklist_start

        logger.info(f"    提取 {len(checklist.items)} 条条款, 耗时{checklist_elapsed:.2f}秒")
        if checklist.sections:
            logger.debug(f"    识别 {len(checklist.sections)} 个章节")
        if checklist.statistics:
            logger.info(f"    统计: {checklist.statistics}")

        # 2. 解析投标书为响应提取
        logger.info(f"  [2/2] 解析投标书响应...")
        bid_start = time.time()
        bid_response = self._parse_bid_response(bid_doc, checklist)
        bid_elapsed = time.time() - bid_start

        logger.info(f"    提取 {len(bid_response.equipment_tables)} 个设备表, 耗时{bid_elapsed:.2f}秒")
        logger.info(f"    提取 {len(bid_response.deviation_table)} 条偏离记录")
        logger.info(f"    提取 {len(bid_response.technical_proposal)} 个技术方案章节")
        logger.info(f"    提取 {len(bid_response.qualification_docs)} 个资质文件引用")

        total_elapsed = time.time() - start_time
        logger.info(f"[Stage 2] 条款对齐完成, 总耗时{total_elapsed:.2f}秒")

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

        从Markdown中提取：
        1. 设备参数表
        2. 偏离表
        3. 技术方案章节
        4. 资质文件列表
        """
        if not bid_doc.markdown:
            logger.warning("投标书Markdown为空")
            return BidResponse(
                bid_id=bid_doc.bid_id,
                tender_id=bid_doc.tender_id,
                project_name=bid_doc.company_name,
                equipment_tables=[],
                deviation_table={},
                technical_proposal={},
                qualification_docs=[],
            )

        markdown = bid_doc.markdown

        # 1. 提取设备参数表
        equipment_tables = self._extract_equipment_tables(markdown)
        logger.info(f"    提取 {len(equipment_tables)} 个设备参数表")

        # 2. 提取偏离表
        deviation_table = self._extract_deviation_table(markdown)
        logger.info(f"    提取 {len(deviation_table)} 条偏离记录")

        # 3. 提取技术方案章节
        technical_proposal = self._extract_technical_sections(markdown)
        logger.info(f"    提取 {len(technical_proposal)} 个技术方案章节")

        # 4. 提取资质文件
        qualification_docs = self._extract_qualification_docs(markdown)
        logger.info(f"    提取 {len(qualification_docs)} 个资质文件")

        return BidResponse(
            bid_id=bid_doc.bid_id,
            tender_id=bid_doc.tender_id,
            project_name=bid_doc.company_name or "未命名项目",
            equipment_tables=equipment_tables,
            deviation_table=deviation_table,
            technical_proposal=technical_proposal,
            qualification_docs=qualification_docs,
        )

    def _extract_equipment_tables(self, markdown: str) -> List[Dict[str, Any]]:
        """
        从Markdown中提取设备参数表

        识别Markdown表格并解析为结构化数据
        """
        import re

        tables = []
        lines = markdown.split('\n')
        current_table = []
        in_table = False
        table_start_line = 0

        for i, line in enumerate(lines):
            # 检测表格起始（Markdown表格有 | 分隔符）
            if '|' in line and line.count('|') >= 2:
                if not in_table:
                    # 尝试查找表格标题（前几行）
                    table_title = self._find_table_title(lines, max(0, i - 5), i)
                    current_table = {
                        "name": table_title or f"设备表{len(tables) + 1}",
                        "start_line": i,
                        "rows": [],
                    }
                    in_table = True
                    table_start_line = i

                # 添加表格行
                current_table["rows"].append(line.strip())
            else:
                if in_table:
                    # 表格结束，解析它
                    parsed_rows = self._parse_markdown_table(current_table["rows"])
                    if parsed_rows:
                        current_table["rows"] = parsed_rows
                        tables.append(current_table)
                    in_table = False

        # 处理最后一个表格
        if in_table and current_table:
            parsed_rows = self._parse_markdown_table(current_table["rows"])
            if parsed_rows:
                current_table["rows"] = parsed_rows
                tables.append(current_table)

        return tables

    def _find_table_title(self, lines: List[str], start: int, end: int) -> Optional[str]:
        """查找表格标题（在表格前几行中）"""
        import re

        # 常见表格标题关键词
        title_keywords = [
            "设备", "参数", "规格", "技术", "配置", "选型", "清单", "主要",
            "冷水机组", "冷却塔", "水泵", "主机", "辅机"
        ]

        for i in range(start, end):
            line = lines[i].strip()
            if any(kw in line for kw in title_keywords):
                # 清理标题（移除#等标记）
                line = re.sub(r'^#+\s*', '', line)
                line = re.sub(r'^[-*]\s*', '', line)
                if line:
                    return line

        return None

    def _parse_markdown_table(self, table_lines: List[str]) -> List[Dict[str, Any]]:
        """解析Markdown表格为结构化行数据"""
        if len(table_lines) < 3:  # 至少需要标题、分隔线、数据行
            return []

        # 提取表头
        header_line = table_lines[0]
        headers = [h.strip() for h in header_line.split('|') if h.strip()]

        if not headers:
            return []

        rows = []
        # 从第3行开始（跳过分隔线）
        for line in table_lines[2:]:
            if '|' not in line:
                continue

            cells = [c.strip() for c in line.split('|') if c.strip()]
            if len(cells) != len(headers):
                continue

            row_data = {}
            parameters = {}
            model = None
            brand = None

            for header, cell in zip(headers, cells):
                # 识别常见列
                header_lower = header.lower()
                if '型号' in header or 'model' in header_lower:
                    model = cell
                elif '品牌' in header or 'brand' in header_lower:
                    brand = cell
                else:
                    # 尝试解析数值
                    value = self._parse_numeric_value(cell)
                    parameters[header] = value if value is not None else cell

            row_data = {
                "model": model,
                "brand": brand,
                "parameters": parameters,
            }
            rows.append(row_data)

        return rows

    def _parse_numeric_value(self, cell: str) -> Optional[float]:
        """尝试解析单元格中的数值"""
        import re

        # 移除单位
        cleaned = re.sub(r'[^\d.\-]', '', cell)
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def _extract_deviation_table(self, markdown: str) -> Dict[str, Any]:
        """提取偏离表"""
        import re

        deviation_table = {}

        # 查找偏离表关键词
        deviation_keywords = ["偏离表", "差异表", "偏差表", "响应表"]
        lines = markdown.split('\n')

        in_deviation_section = False
        for i, line in enumerate(lines):
            if any(kw in line for kw in deviation_keywords):
                in_deviation_section = True
                continue

            if in_deviation_section:
                # 简单提取：查找带"正偏离"、"负偏离"、"无偏离"的行
                if "正偏离" in line or "负偏离" in line or "无偏离" in line:
                    deviation_table[f"line_{i}"] = line.strip()

                # 如果遇到下一个标题，结束
                if line.startswith('#') and i > 10:
                    break

        return deviation_table

    def _extract_technical_sections(self, markdown: str) -> Dict[str, str]:
        """提取技术方案章节"""
        sections = {}
        lines = markdown.split('\n')
        current_section = None
        current_content = []

        # 技术方案相关标题
        tech_section_keywords = [
            "技术方案", "技术说明", "技术描述", "实施方案", "施工方案",
            "调试方案", "验收方案", "培训方案", "售后服务", "质保",
        ]

        for line in lines:
            # 检测标题行
            if line.startswith('#'):
                # 保存之前的章节
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()

                # 检查是否为技术相关章节
                title = line.lstrip('#').strip()
                if any(kw in title for kw in tech_section_keywords):
                    current_section = title
                    current_content = []
                else:
                    current_section = None
                    current_content = []
            elif current_section is not None:
                current_content.append(line)

        # 保存最后一个章节
        if current_section and current_content:
            sections[current_section] = '\n'.join(current_content).strip()

        return sections

    def _extract_qualification_docs(self, markdown: str) -> List[Dict[str, Any]]:
        """提取资质文件列表"""
        import re

        qualifications = []

        # 资质关键词
        qual_keywords = [
            "资质", "证书", "认证", "执照", "许可证", "ISO", "CCC", "CE",
            "质量管理", "环境管理", "职业健康", "安全生产",
        ]

        lines = markdown.split('\n')
        for i, line in enumerate(lines):
            if any(kw in line for kw in qual_keywords):
                # 简单提取：记录包含资质关键词的行
                qualifications.append({
                    "line_number": i,
                    "content": line.strip(),
                })

        return qualifications
