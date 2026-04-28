"""
历史价格查询模块

从 Qdrant 知识库查询历史合同价格，用于与当前报价进行对比分析
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import random
from datetime import datetime, timedelta


@dataclass
class HistoricalPrice:
    """历史价格记录"""
    equipment_name: str
    model_spec: str
    unit_price: Decimal
    contract_date: str
    project_name: str
    supplier: Optional[str] = None
    source: Optional[str] = None
    similarity: float = 0.0


@dataclass
class PriceComparison:
    """价格对比结果"""
    item_name: str
    current_price: Decimal
    historical_avg_price: Optional[Decimal]
    deviation_percent: Optional[float]
    historical_prices: List[HistoricalPrice]
    severity: str  # fatal, major, warning, info
    message: str
    suggestion: str


class HistoricalPriceStore:
    """历史价格存储接口"""

    def __init__(self, collection_name: str = "quote_historical"):
        self.collection_name = collection_name
        self._client = None
        self._embeddings = None

    def _get_client(self):
        """延迟初始化 Qdrant 客户端"""
        if self._client is None:
            from qdrant_client import QdrantClient
            import os

            host = os.getenv('QDRANT_HOST', '')
            port = os.getenv('QDRANT_PORT', '6333')
            api_key = os.getenv('QDRANT_API_KEY', '')

            if not host:
                raise ValueError("QDRANT_HOST not configured")

            if host.startswith('https://'):
                self._client = QdrantClient(url=host, api_key=api_key)
            else:
                self._client = QdrantClient(host=host, port=int(port), api_key=api_key)

        return self._client

    def _get_embeddings(self):
        """延迟初始化 Embeddings"""
        if self._embeddings is None:
            from langchain_rag.vectorstore.qdrant import DashScopeEmbeddings
            self._embeddings = DashScopeEmbeddings()
        return self._embeddings

    def query_historical_prices(
        self,
        equipment_name: str,
        model_spec: Optional[str] = None,
        top_k: int = 5
    ) -> List[HistoricalPrice]:
        """查询历史价格"""
        try:
            client = self._get_client()

            query_text = equipment_name
            if model_spec:
                query_text += " " + model_spec

            embeddings = self._get_embeddings()
            query_vector = embeddings.embed_query(query_text)

            search_results = client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k
            )

            prices = []
            for result in search_results:
                payload = result.payload
                if payload and self._is_historical_price_payload(payload):
                    price = self._parse_historical_price(payload, result.score)
                    if price:
                        prices.append(price)

            return prices

        except Exception as e:
            print(f"[HistoricalPriceStore] Query error: {e}")
            return []

    def _is_historical_price_payload(self, payload: Dict) -> bool:
        """检查 payload 是否为历史价格数据"""
        return 'equipment_name' in payload and 'unit_price' in payload

    def _parse_historical_price(self, payload: Dict, similarity: float) -> Optional[HistoricalPrice]:
        """解析 payload 为 HistoricalPrice 对象"""
        try:
            unit_price = payload.get('unit_price')
            if isinstance(unit_price, str):
                unit_price = Decimal(unit_price)
            elif isinstance(unit_price, (int, float)):
                unit_price = Decimal(str(unit_price))

            return HistoricalPrice(
                equipment_name=payload.get('equipment_name', ''),
                model_spec=payload.get('model_spec', ''),
                unit_price=unit_price,
                contract_date=payload.get('contract_date', ''),
                project_name=payload.get('project_name', ''),
                supplier=payload.get('supplier'),
                source=payload.get('source'),
                similarity=similarity
            )
        except Exception:
            return None

    def get_average_price(
        self,
        equipment_name: str,
        model_spec: Optional[str] = None
    ) -> Optional[Decimal]:
        """获取同类设备的平均价格"""
        prices = self.query_historical_prices(equipment_name, model_spec, top_k=10)
        if not prices:
            return None
        return sum(p.unit_price for p in prices) / len(prices)


class MockHistoricalPriceStore:
    """模拟历史价格存储（用于测试或无历史数据时）"""

    # 典型设备历史价格参考（基于行业数据）
    MOCK_PRICES = {
        "冷水机组": {"base": Decimal("2500000"), "unit": "元/RT"},
        "冷却塔": {"base": Decimal("3500"), "unit": "元/吨处理流量"},
        "水泵": {"base": Decimal("8000"), "unit": "元/台"},
        "配电箱": {"base": Decimal("3000"), "unit": "元/个"},
        "钢管": {"base": Decimal("80"), "unit": "元/米"},
        "阀门": {"base": Decimal("500"), "unit": "元/个"},
    }

    def query_historical_prices(
        self,
        equipment_name: str,
        model_spec: Optional[str] = None,
        top_k: int = 3
    ) -> List[HistoricalPrice]:
        """模拟查询历史价格"""
        prices = []
        name_lower = equipment_name.lower()

        matched_type = None
        for key in self.MOCK_PRICES:
            if key in name_lower:
                matched_type = key
                break

        if matched_type:
            base_price = self.MOCK_PRICES[matched_type]["base"]
            for i in range(top_k):
                variation = Decimal(str(random.uniform(0.8, 1.2)))
                price = base_price * variation
                days_ago = random.randint(0, 730)
                date = datetime.now() - timedelta(days=days_ago)

                prices.append(HistoricalPrice(
                    equipment_name=equipment_name,
                    model_spec=model_spec or "",
                    unit_price=price.quantize(Decimal("0.01")),
                    contract_date=date.strftime("%Y-%m"),
                    project_name=f"历史项目{i+1}",
                    supplier="参考报价",
                    similarity=0.85 - i * 0.05
                ))

        return prices

    def get_average_price(
        self,
        equipment_name: str,
        model_spec: Optional[str] = None
    ) -> Optional[Decimal]:
        """获取平均价格"""
        prices = self.query_historical_prices(equipment_name, model_spec, top_k=10)
        if not prices:
            return None
        return sum(p.unit_price for p in prices) / len(prices)


# 全局实例
_price_store: Optional[Any] = None


def get_historical_price_store(use_mock: bool = True) -> Any:
    """
    获取历史价格存储实例

    Args:
        use_mock: 是否使用模拟数据（当没有真实历史数据时）
    """
    global _price_store

    if _price_store is not None:
        return _price_store

    if use_mock:
        _price_store = MockHistoricalPriceStore()
    else:
        try:
            _price_store = HistoricalPriceStore()
        except Exception as e:
            print(f"[HistoricalPriceStore] Failed to initialize: {e}")
            _price_store = MockHistoricalPriceStore()

    return _price_store
