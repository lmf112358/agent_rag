"""
标书审核配置

包含：
- 章节识别规则
- 设备参数表提取规则
- 评分维度配置
- 核对引擎配置
"""

from typing import Dict, List, Any

# ==================== 章节识别规则 ====================

TENDER_SECTION_PATTERNS = {
    "资格要求": {
        "keywords": ["资格要求", "投标人资格", "合格投标人", "资质要求", "资格预审"],
        "priority": 1,
        "required": True
    },
    "技术要求": {
        "keywords": ["技术要求", "技术规格", "技术参数", "设备规格", "主要技术参数"],
        "priority": 2,
        "required": True,
        "sub_sections": {
            "冷水机组": ["冷水机组", "制冷主机", "离心机", "螺杆机"],
            "冷却塔": ["冷却塔", "冷却水塔", "散热设备"],
            "水泵": ["水泵", "循环泵", "冷冻水泵", "冷却水泵"],
            "自控系统": ["自控系统", "群控", "BA系统", "能效管理", "智能控制"],
            "管路阀门": ["管路", "阀门", "管道", "管件"]
        }
    },
    "评分标准": {
        "keywords": ["评分标准", "评标办法", "打分标准", "技术评分", "商务评分"],
        "priority": 3,
        "required": True
    },
    "商务条款": {
        "keywords": ["商务条款", "合同条款", "报价要求", "付款方式", "交货期", "质保期"],
        "priority": 4,
        "required": True
    }
}

# ==================== 设备参数表提取规则 ====================

EQUIPMENT_TABLE_PATTERNS = {
    "冷水机组": {
        "table_title_keywords": ["冷水机组", "制冷主机", "设备选型", "主要设备"],
        "required_columns": ["型号", "制冷量", "COP", "数量", "品牌"],
        "parameter_mapping": {
            "制冷量": ["制冷量", "额定制冷量", "制冷能力", "冷量"],
            "COP": ["COP", "性能系数", "能效比"],
            "IPLV": ["IPLV", "综合部分负荷性能系数"],
            "输入功率": ["输入功率", "额定功率", "功率"],
            "冷媒": ["冷媒", "制冷剂", "工质"]
        }
    },
    "冷却塔": {
        "table_title_keywords": ["冷却塔", "散热设备"],
        "required_columns": ["型号", "冷却水量", "数量", "品牌"]
    },
    "水泵": {
        "table_title_keywords": ["水泵", "循环泵", "冷冻水泵", "冷却水泵"],
        "required_columns": ["型号", "流量", "扬程", "数量", "品牌"]
    }
}

# ==================== 评分维度配置 ====================

SCORING_DIMENSIONS = {
    "技术响应性": {
        "weight": 0.40,
        "max_score": 40,
        "items_source": ["硬性指标", "评分项-技术"],
        "scoring_rule": "硬性指标不满足则该项0分；评分项按响应程度给分",
        "penalty": "硬性指标不满足可能导致废标"
    },
    "技术先进性": {
        "weight": 0.20,
        "max_score": 20,
        "items_source": ["评分项-先进性"],
        "scoring_rule": "优(20分)/良(16分)/一般(12分)/差(0分)",
        "evaluated_by": "LLM语义评估+人工确认"
    },
    "商务响应性": {
        "weight": 0.20,
        "max_score": 20,
        "items_source": ["商务条款"],
        "scoring_rule": "正偏离不扣分，负偏离按幅度扣分",
        "penalty": "重大负偏离（如交货期超50%）可能导致废标"
    },
    "企业资质": {
        "weight": 0.20,
        "max_score": 20,
        "items_source": ["资质要求"],
        "scoring_rule": "业绩数量×分值+认证加分",
        "evaluated_by": "规则自动计算"
    }
}

# ==================== 核对引擎配置 ====================

COMPLIANCE_ENGINE_CONFIG = {
    "hard_check": {
        "enabled": True,
        "tolerance_percent": 0.01,  # 数值比较的容差百分比
        "operators": {
            ">=": lambda x, y: x >= y,
            "<=": lambda x, y: x <= y,
            ">": lambda x, y: x > y,
            "<": lambda x, y: x < y,
            "==": lambda x, y: x == y,
            "in_range": lambda x, y: y[0] <= x <= y[1],
            "in_list": lambda x, y: x in y
        }
    },
    "soft_check": {
        "enabled": True,
        "confidence_threshold": 0.7,
        "llm_model": "qwen-max",
        "max_tokens": 2000,
        "temperature": 0.1
    },
    "kb_verify": {
        "enabled": True,
        "qdrant_collection": "hvac_equipment",
        "deviation_threshold_percent": 10.0
    }
}

# ==================== 分流决策规则 ====================

AUTO_DECISION_RULES = {
    "auto_pass": {
        "condition": "confidence >= 0.9 AND status == '符合'",
        "action": "自动通过，记录日志"
    },
    "manual_confirm": {
        "condition": "0.7 <= confidence < 0.9 OR status == '部分符合'",
        "action": "人工确认界面，一键采纳/修正/驳回"
    },
    "mandatory_review": {
        "condition": "confidence < 0.7 OR status == '不符合'",
        "action": "强制人工审核，标注原因"
    }
}

# ==================== 报告模板配置 ====================

REPORT_TEMPLATE = {
    "title": "标书合规性审核报告",
    "sections": [
        "项目基本信息",
        "招标条款清单",
        "投标响应提取",
        "合规核对结果",
        "评分汇总",
        "风险分析",
        "修改建议",
        "审核结论"
    ],
    "formats": ["PDF", "JSON", "HTML"],
    "watermark": "AI辅助审核，需人工复核"
}
