"""
Layer 1: 数据清洗与标准化
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Tuple, Optional

from .excel_parser import ExcelParser
from .models import BillItem, BillSection, PipelineContext
from .remark_parser import RemarkParser


class Stage1Cleansing:
    """清洗Excel数据并标准化为BillItem。"""

    # 分部识别关键词
    SECTION_KEYWORDS = {
        "一": {"name": "冷水机房设备", "keywords": ["冷水机房", "冷水机组", "制冷主机", "水泵", "冷却塔"]},
        "二": {"name": "低温冷冻水管道", "keywords": ["冷冻水管道", "冷冻水管", "低温管道", "钢管"]},
        "三": {"name": "冷却水管道", "keywords": ["冷却水管道", "冷却水管", "冷却管道"]},
        "四": {"name": "配电系统", "keywords": ["配电", "电缆", "电气", "桥架"]},
        "五": {"name": "自控系统", "keywords": ["自控", "BA系统", "DDC", "传感器", "线缆"]},
    }

    def __init__(self) -> None:
        self.excel_parser = ExcelParser()
        self.remark_parser = RemarkParser()

    def run(self, context: PipelineContext) -> Tuple[PipelineContext, List[Dict]]:
        alerts: List[Dict] = []

        sheet_results = self.excel_parser.parse(context.excel_path)
        context.sheets = sheet_results

        items: List[BillItem] = []
        sections: List[BillSection] = []
        sequence_seen: Dict[str, int] = {}

        current_section: Optional[Dict] = None
        current_section_items: List[BillItem] = []

        for sheet in sheet_results:
            phase = sheet.phase

            for row in sheet.rows:
                item_name = self._text(row.get("item_name"))
                sequence = self._text(row.get("sequence"))

                # 跳过空的行
                if not item_name and not sequence:
                    continue

                # 检查是否是分部标题行（如"一、冷水机房设备"）
                is_section_header = self._is_section_header(sequence, item_name)

                if is_section_header:
                    # 保存上一个分部
                    if current_section and current_section_items:
                        section = self._build_section(current_section, current_section_items, phase)
                        if section:
                            sections.append(section)

                    # 开始新的分部
                    section_info = self._parse_section_header(sequence, item_name)
                    current_section = section_info
                    current_section_items = []
                    continue

                # 跳过汇总行（小计、直接费、措施费、税金、合计）
                if self._is_summary_row(item_name):
                    continue

                # 创建清单项
                item = BillItem(
                    sequence=sequence,
                    section=current_section["name"] if current_section else "",
                    item_name=item_name,
                    item_features=self._text(row.get("item_features")),
                    brand=self._opt_text(row.get("brand")),
                    model_spec=self._opt_text(row.get("model_spec")),
                    unit=self._text(row.get("unit")),
                    quantity=self._decimal_or_zero(row.get("quantity")),
                    material_unit_price=self._decimal_or_none(row.get("material_unit_price")),
                    labor_unit_price=self._decimal_or_none(row.get("labor_unit_price")),
                    material_total=self._decimal_or_none(row.get("material_total")),
                    labor_total=self._decimal_or_none(row.get("labor_total")),
                    remarks=self._opt_text(row.get("remarks")),
                    phase=phase,
                    row_index=int(row.get("_row_index", 0) or 0),
                )

                parsed_remark = self.remark_parser.parse(item.remarks)
                item.is_owner_supply = parsed_remark["is_owner_supply"]
                item.owner_supply_status = "甲供" if item.is_owner_supply else "非甲供"
                item.tech_tags = parsed_remark["tech_tags"]
                if parsed_remark["phase"] in ("一期", "二期"):
                    item.phase = parsed_remark["phase"]

                item.item_total = (item.material_total or Decimal("0")) + (item.labor_total or Decimal("0"))

                if sequence:
                    sequence_seen[sequence] = sequence_seen.get(sequence, 0) + 1

                if item.quantity is None or item.quantity == 0:
                    alerts.append(
                        {
                            "type": "工程量缺失",
                            "severity": "major",
                            "item": item.item_name,
                            "message": f"第{item.row_index}行工程量为空或零",
                            "suggestion": "补充有效工程量",
                        }
                    )

                current_section_items.append(item)
                items.append(item)

        # 保存最后一个分部
        if current_section and current_section_items:
            section = self._build_section(current_section, current_section_items, phase)
            if section:
                sections.append(section)

        # 序号重复检查
        for seq, count in sequence_seen.items():
            if count > 1 and not self._is_numeric_sequence(seq):
                alerts.append(
                    {
                        "type": "序号重复",
                        "severity": "warning",
                        "item": seq,
                        "message": f"序号 {seq} 出现 {count} 次",
                        "suggestion": "检查并修正重复序号",
                    }
                )

        context.items = items
        context.sections = sections
        return context, alerts

    def _is_section_header(self, sequence: str, item_name: str) -> bool:
        """检查是否是分部标题行"""
        # 纯中文数字序号（分部标记）
        if sequence in self.SECTION_KEYWORDS:
            return True
        # 检查名称是否以分部关键词开头
        for sec_key, sec_info in self.SECTION_KEYWORDS.items():
            if sec_key in item_name or any(kw in item_name for kw in sec_info["keywords"]):
                # 如果名称中包含分部关键词且序号为空或很短，可能是分部行
                if not sequence or len(sequence) <= 2:
                    return True
        return False

    def _is_numeric_sequence(self, sequence: str) -> bool:
        """检查序号是否是小数（通常是分部内的分类序号）"""
        if not sequence:
            return False
        try:
            float(sequence)
            return True
        except Exception:
            return False

    def _is_summary_row(self, item_name: str) -> bool:
        """检查是否是汇总行（小计、直接费、措施费、税金、合计等）"""
        summary_keywords = ["小计", "直接费", "措施费", "税金", "合计", "总价", "总计"]
        if not item_name:
            return False
        return any(kw in item_name for kw in summary_keywords)

    def _parse_section_header(self, sequence: str, item_name: str) -> Dict:
        """解析分部标题行"""
        # 尝试从序号匹配
        if sequence in self.SECTION_KEYWORDS:
            return {
                "id": sequence,
                "name": self.SECTION_KEYWORDS[sequence]["name"]
            }
        # 尝试从名称匹配
        for sec_key, sec_info in self.SECTION_KEYWORDS.items():
            if any(kw in item_name for kw in sec_info["keywords"]):
                return {
                    "id": sec_key,
                    "name": sec_info["name"]
                }
        # 默认解析
        return {
            "id": sequence if sequence else "未知",
            "name": item_name if item_name else "未知分部"
        }

    def _build_section(self, section_info: Dict, items: List[BillItem], phase: str) -> Optional[BillSection]:
        """构建分部对象"""
        if not items:
            return None

        subtotal_material = sum((item.material_total or Decimal("0")) for item in items)
        subtotal_labor = sum((item.labor_total or Decimal("0")) for item in items)

        return BillSection(
            section_id=section_info["id"],
            section_name=section_info["name"],
            items=items,
            subtotal_material=subtotal_material,
            subtotal_labor=subtotal_labor,
            phase=phase,
        )

    def _text(self, value) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _opt_text(self, value):
        text = self._text(value)
        return text if text else None

    def _decimal_or_none(self, value):
        if value is None:
            return None
        text = str(value).strip()
        if text in ("", "-", "—"):
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return None

    def _decimal_or_zero(self, value):
        parsed = self._decimal_or_none(value)
        return parsed if parsed is not None else Decimal("0")
