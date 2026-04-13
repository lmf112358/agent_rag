"""
RAG检索链模块
实现基础RAG + 高级检索策略（Query Transformation, Reranking等）
"""

from typing import List, Optional, Dict, Any, Callable
from langchain.schema import Document, BaseRetriever
from langchain.callbacks.manager import CallbackManagerForRetrieverRun, Callbacks
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import (
    DocumentCompressorPipeline,
    LLMChainExtractor,
    LLMChainFilter,
)
from langchain.chains import RetrievalQA, ConversationalRetrievalChain
from langchain.chains.base import Chain
from langchain.prompts import PromptTemplate, ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage
from pydantic import Field

from llm.qwen import ChatQwen, get_qwen_chat
from vectorstore.qdrant import QdrantVectorStore, QdrantRetriever, DashScopeEmbeddings
from document.processor import ChunkConfig


class QueryTransformer:
    """Query转换器 - 扩展查询术语"""

    def __init__(
        self,
        llm: Optional[ChatQwen] = None,
        synonyms: Optional[Dict[str, List[str]]] = None,
    ):
        self.llm = llm or get_qwen_chat()
        self.synonyms = synonyms or self._default_synonyms()

    def _default_synonyms(self) -> Dict[str, List[str]]:
        """默认暖通空调术语同义词表"""
        return {
            "中央空调": ["冷水机组", "暖通空调", "HVAC", "空调系统", "制冷系统"],
            "冷水机组": ["冷水机", "制冷机组", "水冷机组", "风冷机组"],
            "冷却塔": ["凉水塔", "冷却水塔", "蒸发冷却塔"],
            "COP": ["能效比", "制冷性能系数", "能源效率"],
            "风机盘管": ["FCU", "空气处理机组", "AHU"],
            "风冷热泵": ["空气源热泵", "热泵机组"],
            "能效": ["能源效率", "能耗", "节能"],
            "投标": ["招标", "标书", "投标文件"],
            "报价": ["价格", "报价单", "工程造价"],
        }

    def expand_query(self, query: str) -> str:
        """扩展查询术语"""
        expanded = query

        for term, synonyms in self.synonyms.items():
            if term in expanded:
                for syn in synonyms:
                    if syn not in expanded:
                        expanded += f" OR {syn}"

        return expanded

    def rewrite_query(self, query: str) -> str:
        """使用LLM重写查询（更智能）"""
        prompt = f"""你是一个工业暖通空调领域的专家。请将用户的问题改写得更精确、更适合检索知识库。

原始问题: {query}

要求:
1. 添加专业术语
2. 明确技术上下文
3. 可以添加同义扩展
4. 保持原意不变

改写后的问题:"""

        response = self.llm.invoke([HumanMessage(content=prompt)])
        return response.content.strip()

    def transform(self, query: str, use_llm: bool = False) -> str:
        """转换查询"""
        if use_llm:
            return self.rewrite_query(query)
        return self.expand_query(query)


class Reranker:
    """重排序器 - 优化检索结果"""

    def __init__(
        self,
        llm: Optional[ChatQwen] = None,
        top_k: int = 5,
    ):
        self.llm = llm or get_qwen_chat()
        self.top_k = top_k

    def rerank(
        self,
        query: str,
        documents: List[Document],
    ) -> List[Document]:
        """对文档进行重排序"""
        if not documents:
            return []

        if len(documents) <= self.top_k:
            return documents

        scored_docs = []
        for doc in documents:
            prompt = f"""请评估以下文档与查询的相关程度。

查询: {query}

文档内容:
{doc.page_content[:500]}

请从以下方面评估(1-10分):
1. 主题相关性
2. 信息完整性
3. 专业程度

直接输出分数(只需数字):"""

            try:
                response = self.llm.invoke([HumanMessage(content=prompt)])
                score = self._parse_score(response.content)
                scored_docs.append((doc, score))
            except Exception:
                scored_docs.append((doc, 0))

        scored_docs.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in scored_docs[: self.top_k]]

    def _parse_score(self, content: str) -> float:
        """解析分数"""
        import re
        numbers = re.findall(r"\d+\.?\d*", content)
        if numbers:
            return float(numbers[0])
        return 0.0


class BaseRAGChain(Chain):
    """基础RAG链"""

    retriever: BaseRetriever
    llm: ChatQwen
    prompt: ChatPromptTemplate
    return_source_documents: bool = True

    @property
    def input_keys(self) -> List[str]:
        return ["query"]

    @property
    def output_keys(self) -> List[str]:
        if self.return_source_documents:
            return ["result", "source_documents"]
        return ["result"]

    def _call(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行RAG链"""
        query = inputs["query"]

        docs = self.retriever.get_relevant_documents(query)

        context = "\n\n".join([doc.page_content for doc in docs])

        system_prompt = self.prompt.messages[0].content
        human_prompt = self.prompt.messages[1].content

        messages = [
            SystemMessage(content=system_prompt.format(context=context)),
            HumanMessage(content=human_prompt.format(question=query)),
        ]

        response = self.llm.invoke(messages)

        result = {"result": response.content}
        if self.return_source_documents:
            result["source_documents"] = docs

        return result


class AdvancedRAGChain:
    """高级RAG链 - 包含完整检索增强流程"""

    def __init__(
        self,
        vectorstore: QdrantVectorStore,
        llm: Optional[ChatQwen] = None,
        chunk_config: Optional[ChunkConfig] = None,
        retrieval_top_k: int = 10,
        rerank_top_k: int = 5,
        min_relevance_score: float = 0.75,
    ):
        self.vectorstore = vectorstore
        self.llm = llm or get_qwen_chat()
        self.query_transformer = QueryTransformer(llm=self.llm)
        self.reranker = Reranker(llm=self.llm, top_k=rerank_top_k)
        self.retrieval_top_k = retrieval_top_k
        self.rerank_top_k = rerank_top_k
        self.min_relevance_score = min_relevance_score
        self.chunk_config = chunk_config

    def retrieve(self, query: str, use_query_transform: bool = True) -> List[Document]:
        """检索相关文档"""
        if use_query_transform:
            transformed_query = self.query_transformer.transform(query)
        else:
            transformed_query = query

        docs = self.vectorstore.similarity_search(
            transformed_query,
            k=self.retrieval_top_k,
        )

        reranked_docs = self.reranker.rerank(query, docs)

        return reranked_docs

    def get_relevant_documents(
        self,
        query: str,
        use_query_transform: bool = True,
    ) -> List[Document]:
        """获取相关文档"""
        return self.retrieve(query, use_query_transform)

    def invoke(
        self,
        query: str,
        use_query_transform: bool = True,
        return_context: bool = False,
    ) -> Dict[str, Any]:
        """完整RAG流程"""
        docs = self.retrieve(query, use_query_transform)

        context = "\n\n".join([doc.page_content for doc in docs])

        system_prompt = f"""你是一个专业的工业暖通空调领域专家。基于提供的上下文信息，回答用户的问题。

重要原则:
1. 只基于提供的上下文信息回答，不要编造信息
2. 如果上下文中没有相关信息，明确告知用户
3. 引用相关文档时标注来源
4. 保持专业、严谨的技术风格

提供的上下文:
{context}
"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=query),
        ]

        response = self.llm.invoke(messages)

        result = {"answer": response.content}

        if return_context:
            result["context"] = docs

        return result


class ConversationalRAGChain:
    """对话式RAG链 - 支持多轮对话"""

    def __init__(
        self,
        vectorstore: QdrantVectorStore,
        llm: Optional[ChatQwen] = None,
        memory: Optional[Any] = None,
    ):
        self.vectorstore = vectorstore
        self.llm = llm or get_qwen_chat()
        self.memory = memory
        self.chat_history: List[BaseMessage] = []

    def add_to_history(self, role: str, content: str):
        """添加对话历史"""
        if role == "user":
            self.chat_history.append(HumanMessage(content=content))
        else:
            self.chat_history.append(AIMessage(content=content))

    def invoke(self, query: str) -> Dict[str, Any]:
        """执行对话RAG"""
        docs = self.vectorstore.similarity_search(query, k=5)
        context = "\n\n".join([doc.page_content for doc in docs])

        history_context = ""
        if self.chat_history:
            history_context = "\n\n对话历史:\n" + "\n".join([
                f"{'用户' if isinstance(m, HumanMessage) else '助手'}: {m.content}"
                for m in self.chat_history[-6:]
            ])

        system_prompt = f"""你是一个专业的工业暖通空调领域专家。基于提供的上下文信息和对话历史，回答用户的问题。

重要原则:
1. 只基于提供的上下文信息回答
2. 参考对话历史保持连贯性
3. 如果上下文中没有相关信息，明确告知

提供的上下文:
{context}
{history_context}
"""

        messages = [
            SystemMessage(content=system_prompt),
            *self.chat_history[-6:],
            HumanMessage(content=query),
        ]

        response = self.llm.invoke(messages)
        self.add_to_history("user", query)
        self.add_to_history("assistant", response.content)

        return {
            "answer": response.content,
            "source_documents": docs,
        }

    def clear_history(self):
        """清空对话历史"""
        self.chat_history = []


class RAGPipelineFactory:
    """RAG流水线工厂"""

    @staticmethod
    def create_basic_rag(
        vectorstore: QdrantVectorStore,
        llm: Optional[ChatQwen] = None,
    ) -> BaseRAGChain:
        """创建基础RAG链"""
        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(
                "你是一个专业的工业暖通空调领域专家。基于提供的上下文信息，回答用户的问题。\n\n提供的上下文:\n{context}"
            ),
            HumanMessagePromptTemplate.from_template("{question}"),
        ])

        retriever = QdrantRetriever(
            vectorstore=vectorstore,
            k=5,
        )

        return BaseRAGChain(
            retriever=retriever,
            llm=llm or get_qwen_chat(),
            prompt=prompt,
        )

    @staticmethod
    def create_advanced_rag(
        vectorstore: QdrantVectorStore,
        llm: Optional[ChatQwen] = None,
        **kwargs,
    ) -> AdvancedRAGChain:
        """创建高级RAG链"""
        return AdvancedRAGChain(
            vectorstore=vectorstore,
            llm=llm,
            **kwargs,
        )

    @staticmethod
    def create_conversational_rag(
        vectorstore: QdrantVectorStore,
        llm: Optional[ChatQwen] = None,
    ) -> ConversationalRAGChain:
        """创建对话式RAG链"""
        return ConversationalRAGChain(
            vectorstore=vectorstore,
            llm=llm,
        )
