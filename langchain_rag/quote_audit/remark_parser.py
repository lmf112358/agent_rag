"""
备注语义解析器

识别特殊标记：甲供设备、分期标记、技术要求标签
"""

from typing import Optional, Dict, List
from .config import (
    OWNER_SUPPLY_KEYWORDS,
    PHASE_REMARK_KEYWORDS,
    TECH_KEYWORDS,
)
from .models import BillItem


class RemarkParser:
    """解析备注字段，识别特殊标记"""

    def parse(self, remark: Optional[str]) -> Dict:
        """解析备注，返回标记信息"""
        if not remark or not remark.strip():
            return {
                "is_owner_supply": False,
                "phase": None,
                "tech_tags": [],
                "raw": "",
            }

        remark = remark.strip()

        # 甲供判断
        is_owner_supply = any(kw in remark for kw in OWNER_SUPPLY_KEYWORDS)

        # 分期判断
        phase = None
        for ph, keywords in PHASE_REMARK_KEYWORDS.items():
            if any(kw in remark for kw in keywords):
                phase = ph
                break

        # 技术标记
        tech_tags = []
        for tag, keywords in TECH_KEYWORDS.items():
            if any(kw in remark for kw in keywords):
                tech_tags.append(tag)

        return {
            "is_owner_supply": is_owner_supply,
            "phase": phase,
            "tech_tags": tech_tags,
            "raw": remark,
        }

    def validate_owner_supply(self, item: BillItem) -> List[Dict]:
        """
        校验甲供设备的价格处理是否正确
        规则：甲供设备主材单价应为0或空，仅计取安装费（人工费）
        """
        parsed = self.parse(item.remarks)
        alerts = []

        if parsed["is_owner_supply"]:
            # 甲供设备不应有主材单价
            if item.material_unit_price and item.material_unit_price > 0:
                alerts.append({
                    "type": "甲供设备价格异常",
                    "item": item.item_name,
                    "severity": "major",
                    "message": f"甲供设备不应有主材单价，当前主材单价={item.material_unit_price}",
                    "suggestion": "主材单价应设为0，仅保留人工费",
                })

            # 甲供设备应有安装费
            if not item.labor_unit_price or item.labor_unit_price == 0:
                alerts.append({
                    "type": "甲供设备安装费缺失",
                    "item": item.item_name,
                    "severity": "warning",
                    "message": "甲供设备应计取安装费（人工费）",
                    "suggestion": "补充安装费",
                })

        return alerts
