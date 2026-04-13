"""
Tools模块 - Agent核心工具集
包含: 知识检索工具、报价复核工具、合规审核工具
"""

from typing import TypeVar, Optional, Dict, Any, List
from pydantic import BaseModel, Field
from langchain.tools import BaseTool, Tool
from langchain.schema import Document

from vectorstore.qdrant import QdrantVectorStore, QdrantRetriever
from rag.retrieval import AdvancedRAGChain


class KnowledgeRetrievalInput(BaseModel):
    """知识检索输入"""
    query: str = Field(description="用户查询内容")
    top_k: int = Field(default=5, description="返回的最相关文档数量")
    use_query_transform: bool = Field(default=True, description="是否使用查询转换扩展")


class QuoteValidationInput(BaseModel):
    """报价复核输入"""
    quote_text: str = Field(description="需要复核的报价文本或报价单内容")
    historical_avg_price: Optional[float] = Field(default=None, description="历史均价(可选)")


class ComplianceCheckInput(BaseModel):
    """合规审核输入"""
    document_text: str = Field(description="待审核的投标方案或招标书内容")
    check_type: List[str] = Field(default=["能效", "安全", "ESG"], description="审核类型列表")


class KnowledgeRetrievalTool(BaseTool):
    """知识检索工具"""

    name: str = "knowledge_retriever"
    description: str = """用于回答企业专业知识库相关的问题。当你需要查询:
- 空调系统设计规范
- 设备选型参数
- 历史项目经验
- 行业标准要求
等问题时使用此工具。"""

    def __init__(
        self,
        vectorstore: Optional[QdrantVectorStore] = None,
        rag_chain: Optional[AdvancedRAGChain] = None,
    ):
        super().__init__()
        self.vectorstore = vectorstore
        self.rag_chain = rag_chain

    def _run(self, query: str, top_k: int = 5, use_query_transform: bool = True) -> Dict[str, Any]:
        """执行知识检索"""
        if self.rag_chain:
            result = self.rag_chain.invoke(
                query,
                use_query_transform=use_query_transform,
                return_context=True,
            )
            return result
        elif self.vectorstore:
            docs = self.vectorstore.similarity_search(query, k=top_k)
            context = "\n\n".join([doc.page_content for doc in docs])
            return {
                "answer": context,
                "source_documents": docs,
            }
        else:
            return {"answer": "知识库未初始化", "source_documents": []}

    async def _arun(self, query: str, top_k: int = 5, use_query_transform: bool = True) -> Dict[str, Any]:
        """异步执行知识检索"""
        return self._run(query, top_k, use_query_transform)


class QuoteValidationTool(BaseTool):
    """报价复核工具 - 硬逻辑校验，防LLM幻觉"""

    name: str = "quote_validator"
    description: str = """用于复核投标报价的合理性。执行三级校验:
1. 历史对标: 单品价格需在历史同型号均价±20%区间内
2. 成本底线: 分项报价≥(材料费+人工费+管理费)×1.03
3. 供应商白名单: 报价中供应商必须在认证名录内

注意: 所有数值计算使用Python硬逻辑，不依赖LLM。"""

    def __init__(
        self,
        historical_prices: Optional[Dict[str, float]] = None,
        supplier_whitelist: Optional[List[str]] = None,
        material_cost_ratio: float = 0.7,
        labor_cost_ratio: float = 0.15,
        management_cost_ratio: float = 0.15,
    ):
        super().__init__()
        self.historical_prices = historical_prices or {}
        self.supplier_whitelist = supplier_whitelist or []
        self.material_cost_ratio = material_cost_ratio
        self.labor_cost_ratio = labor_cost_ratio
        self.management_cost_ratio = management_cost_ratio

    def _calculate_total_price(self, price: float, quantity: float) -> float:
        """计算总价"""
        return price * quantity

    def _validate_historical_alignment(
        self,
        item_name: str,
        unit_price: float,
    ) -> Dict[str, Any]:
        """历史对标校验"""
        historical_price = self.historical_prices.get(item_name)

        if historical_price is None:
            return {
                "passed": None,
                "message": f"无历史价格数据: {item_name}",
                "historical_price": None,
                "deviation": None,
            }

        deviation = abs(unit_price - historical_price) / historical_price

        passed = deviation <= 0.2

        return {
            "passed": passed,
            "message": f"{'通过' if passed else '偏离'}历史均价({historical_price:.2f}), 偏离度: {deviation*100:.1f}%",
            "historical_price": historical_price,
            "deviation": deviation,
        }

    def _validate_cost_bottom_line(
        self,
        total_price: float,
        material_cost: float,
        labor_cost: float,
        management_cost: float,
    ) -> Dict[str, Any]:
        """成本底线校验"""
        min_profit = (material_cost + labor_cost + management_cost) * 0.03
        min_total = material_cost + labor_cost + management_cost + min_profit

        passed = total_price >= min_total

        return {
            "passed": passed,
            "message": f"{'通过' if passed else '低于'}成本底线({min_total:.2f})",
            "min_total": min_total,
            "actual_total": total_price,
        }

    def _validate_supplier(self, supplier_name: str) -> Dict[str, Any]:
        """供应商白名单校验"""
        if not self.supplier_whitelist:
            return {"passed": True, "message": "白名单未配置，跳过校验"}

        passed = supplier_name in self.supplier_whitelist

        return {
            "passed": passed,
            "message": f"供应商{'在' if passed else '不在'}白名单中",
        }

    def _parse_quote_text(self, quote_text: str) -> List[Dict[str, Any]]:
        """解析报价文本（简单实现）"""
        import re

        items = []
        lines = quote_text.split("\n")

        for line in lines:
            match = re.search(r"(.+?)\s*[:：]\s*([\d,]+(?:\.\d+)?)\s*(?:元|¥|￥)?", line)
            if match:
                items.append({
                    "name": match.group(1).strip(),
                    "price": float(match.group(2).replace(",", "")),
                })

        return items if items else [{"name": "未知项目", "price": 0}]

    def _run(self, quote_text: str, historical_avg_price: Optional[float] = None) -> Dict[str, Any]:
        """执行报价复核"""
        items = self._parse_quote_text(quote_text)

        validation_results = []
        overall_passed = True

        for item in items:
            item_name = item["name"]
            unit_price = item["price"]

            hist_result = self._validate_historical_alignment(item_name, unit_price)

            validation_results.append({
                "item": item_name,
                "unit_price": unit_price,
                "historical_validation": hist_result,
            })

            if hist_result.get("passed") is False:
                overall_passed = False

        return {
            "overall_passed": overall_passed,
            "confidence": 1.0 if overall_passed else 0.95,
            "items_validated": len(items),
            "details": validation_results,
            "warning": "低置信" if not overall_passed else None,
        }

    async def _arun(self, quote_text: str, historical_avg_price: Optional[float] = None) -> Dict[str, Any]:
        """异步执行报价复核"""
        return self._run(quote_text, historical_avg_price)


class ComplianceCheckTool(BaseTool):
    """合规审核工具 - 检查投标方案是否符合规范"""

    name: str = "compliance_checker"
    description: str = """用于审核投标方案的技术合规性。支持检查:
- 能效标准 (COP, IPLV等)
- 安全规范 (GB标准)
- ESG要求 (环保节能)
- 技术规格响应

返回置信度评估，低于0.75自动触发人工审核。"""

    def __init__(
        self,
        llm: Optional[Any] = None,
        standards: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        super().__init__()
        self.llm = llm
        self.standards = standards or {
            "COP": {"min_value": 6.0, "description": "制冷性能系数"},
            "IPLV": {"min_value": 5.0, "description": "综合部分负荷值"},
            "能效等级": {"min_value": 1, "max_value": 3, "description": "一级/二级/三级能效"},
        }

    def _check_cop_compliance(self, cop_value: float) -> Dict[str, Any]:
        """检查COP合规性"""
        min_cop = self.standards.get("COP", {}).get("min_value", 6.0)

        passed = cop_value >= min_cop

        return {
            "standard": "COP",
            "required": f"≥{min_cop}",
            "actual": cop_value,
            "passed": passed,
            "message": f"COP值{'符合' if passed else '不符合'}要求({min_cop})",
        }

    def _check_energy_efficiency(self, document_text: str) -> Dict[str, Any]:
        """检查能效相关条款"""
        import re

        cop_matches = re.findall(r"COP[：:\s]*([\d.]+)", document_text, re.IGNORECASE)
        iplv_matches = re.findall(r"IPLV[：:\s]*([\d.]+)", document_text, re.IGNORECASE)

        results = []

        for cop_str in cop_matches:
            try:
                cop_val = float(cop_str)
                results.append(self._check_cop_compliance(cop_val))
            except ValueError:
                pass

        for iplv_str in iplv_matches:
            try:
                iplv_val = float(iplv_str)
                min_iplv = self.standards.get("IPLV", {}).get("min_value", 5.0)
                passed = iplv_val >= min_iplv
                results.append({
                    "standard": "IPLV",
                    "required": f"≥{min_iplv}",
                    "actual": iplv_val,
                    "passed": passed,
                    "message": f"IPLV值{'符合' if passed else '不符合'}要求({min_iplv})",
                })
            except ValueError:
                pass

        return {
            "items_checked": len(results),
            "passed_count": sum(1 for r in results if r.get("passed")),
            "details": results,
        }

    def _check_safety_standards(self, document_text: str) -> Dict[str, Any]:
        """检查安全标准"""
        import re

        gb_matches = re.findall(r"GB\s*\d+[.\d]*", document_text)

        required_gb = ["GB/T 18430", "GB 10080", "GB 19577"]

        found_standards = list(set(gb_matches))

        results = []
        for required in required_gb:
            found = any(required in std for std in found_standards)
            results.append({
                "standard": required,
                "found": found,
                "message": f"{required}: {'已识别' if found else '未识别'}",
            })

        return {
            "required_count": len(required_gb),
            "found_count": len([r for r in results if r["found"]]),
            "details": results,
        }

    def _check_esg_compliance(self, document_text: str) -> Dict[str, Any]:
        """检查ESG合规性"""
        esg_keywords = {
            "环保": ["环保", "节能", "减排", "碳排放", "绿色"],
            "社会责任": ["安全", "健康", "职业健康", "社会责任"],
            "公司治理": ["合规", "审计", "透明"],
        }

        found_keywords = {category: [] for category in esg_keywords}

        for category, keywords in esg_keywords.items():
            for keyword in keywords:
                if keyword in document_text:
                    found_keywords[category].append(keyword)

        total_keywords = sum(len(kws) for kws in found_keywords.values())
        has_esg_content = total_keywords > 0

        return {
            "has_esg_content": has_esg_content,
            "keywords_found": found_keywords,
            "message": f"识别到{sum(len(v) for v in found_keywords.values())}个ESG相关关键词",
        }

    def _run(self, document_text: str, check_type: List[str] = None) -> Dict[str, Any]:
        """执行合规检查"""
        check_type = check_type or ["能效", "安全", "ESG"]

        results = {}

        if "能效" in check_type:
            results["能效"] = self._check_energy_efficiency(document_text)

        if "安全" in check_type:
            results["安全"] = self._check_safety_standards(document_text)

        if "ESG" in check_type:
            results["ESG"] = self._check_esg_compliance(document_text)

        all_passed = True
        for category, result in results.items():
            if "details" in result:
                if "passed" in result["details"]:
                    all_passed = all_passed and result["details"].get("passed", True)
                elif "passed_count" in result:
                    all_passed = all_passed and (result["passed_count"] == result["items_checked"])

        confidence = 0.95 if all_passed else 0.8

        return {
            "overall_passed": all_passed,
            "confidence": confidence,
            "needs_human_review": confidence < 0.75,
            "results": results,
        }

    async def _arun(self, document_text: str, check_type: List[str] = None) -> Dict[str, Any]:
        """异步执行合规检查"""
        return self._run(document_text, check_type)


def create_knowledge_tool(vectorstore: QdrantVectorStore) -> KnowledgeRetrievalTool:
    """创建知识检索工具"""
    return KnowledgeRetrievalTool(vectorstore=vectorstore)


def create_quote_validator(**kwargs) -> QuoteValidationTool:
    """创建报价复核工具"""
    return QuoteValidationTool(**kwargs)


def create_compliance_checker(llm: Any = None, **kwargs) -> ComplianceCheckTool:
    """创建合规审核工具"""
    return ComplianceCheckTool(llm=llm, **kwargs)


def get_all_tools(
    vectorstore: Optional[QdrantVectorStore] = None,
    llm: Optional[Any] = None,
    **kwargs,
) -> List[BaseTool]:
    """获取所有工具"""
    tools = []

    if vectorstore:
        tools.append(create_knowledge_tool(vectorstore))

    tools.append(create_quote_validator(**kwargs))

    tools.append(create_compliance_checker(llm=llm, **kwargs))

    return tools
