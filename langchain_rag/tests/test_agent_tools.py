"""
Agent Tools 模块测试
"""
import pytest
from unittest.mock import MagicMock, patch

from langchain_rag.tools.agent_tools import (
    QuoteValidationTool,
    ComplianceCheckTool,
    create_quote_validator,
    create_compliance_checker,
)


class TestQuoteValidationTool:
    """测试报价复核工具"""

    def test_initialization(self):
        """测试基本初始化"""
        tool = QuoteValidationTool(
            historical_prices={"空调": 10000.0},
            supplier_whitelist=["供应商A", "供应商B"],
        )

        assert tool.name == "quote_validator"
        assert "空调" in tool.historical_prices
        assert len(tool.supplier_whitelist) == 2

    def test_parse_quote_text(self):
        """测试报价文本解析"""
        tool = QuoteValidationTool()
        quote_text = """
        空调主机: 50000元
        安装费: 5000
        """

        items = tool._parse_quote_text(quote_text)

        assert len(items) >= 1
        assert any("空调" in item["name"] for item in items)

    def test_validate_historical_alignment(self):
        """测试历史对标校验"""
        tool = QuoteValidationTool(historical_prices={"空调": 10000.0})

        # 在允许范围内
        result_pass = tool._validate_historical_alignment("空调", 11000.0)
        assert result_pass["passed"] is True

        # 超出范围
        result_fail = tool._validate_historical_alignment("空调", 15000.0)
        assert result_fail["passed"] is False

    def test_run_empty_quote(self):
        """测试空报价输入"""
        tool = QuoteValidationTool()
        result = tool._run("")

        assert "overall_passed" in result
        assert "items_validated" in result


class TestComplianceCheckTool:
    """测试合规审核工具"""

    def test_initialization(self):
        """测试基本初始化"""
        tool = ComplianceCheckTool()

        assert tool.name == "compliance_checker"
        assert "COP" in tool.standards

    def test_check_cop_compliance(self):
        """测试 COP 合规检查"""
        tool = ComplianceCheckTool()

        result_pass = tool._check_cop_compliance(6.5)
        assert result_pass["passed"] is True

        result_fail = tool._check_cop_compliance(5.5)
        assert result_fail["passed"] is False

    def test_check_energy_efficiency(self):
        """测试能效检查"""
        tool = ComplianceCheckTool()
        doc_text = "COP: 6.2, IPLV: 5.1"

        result = tool._check_energy_efficiency(doc_text)

        assert "items_checked" in result
        assert "passed_count" in result

    def test_check_esg_compliance(self):
        """测试 ESG 合规检查"""
        tool = ComplianceCheckTool()
        doc_text = "本方案采用环保节能技术，符合绿色要求。"

        result = tool._check_esg_compliance(doc_text)

        assert "has_esg_content" in result
        assert result["has_esg_content"] is True

    def test_run_full_check(self):
        """测试完整合规检查"""
        tool = ComplianceCheckTool()
        doc_text = "COP: 6.0, IPLV: 5.0, GB/T 18430, 环保节能"

        result = tool._run(doc_text, check_type=["能效", "安全", "ESG"])

        assert "overall_passed" in result
        assert "confidence" in result
        assert "results" in result


class TestToolFactories:
    """测试工具工厂函数"""

    def test_create_quote_validator(self):
        """测试创建报价复核工具"""
        tool = create_quote_validator(
            historical_prices={"测试": 100.0},
        )
        assert isinstance(tool, QuoteValidationTool)
        assert "测试" in tool.historical_prices

    def test_create_compliance_checker(self):
        """测试创建合规审核工具"""
        tool = create_compliance_checker()
        assert isinstance(tool, ComplianceCheckTool)
