"""
快速启动示例
演示如何使用Agentic RAG系统
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_rag.llm.qwen import ChatQwen, get_qwen_chat
from langchain_rag.vectorstore.qdrant import QdrantVectorStore, DashScopeEmbeddings, QdrantVectorStoreFactory
from langchain_rag.document.processor import DocumentProcessor, ChunkConfig, load_and_process_documents
from langchain_rag.rag.retrieval import AdvancedRAGChain, ConversationalRAGChain
from langchain_rag.agent.core import AgenticRAGAgent, ReActAgent
from langchain_rag.tools.agent_tools import get_all_tools
from langchain_rag.config.settings import config


def example_01_basic_rag():
    """示例1: 基础RAG问答"""
    print("\n" + "=" * 60)
    print("示例1: 基础RAG问答")
    print("=" * 60)

    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        print("请设置 DASHSCOPE_API_KEY 环境变量")
        return

    llm = get_qwen_chat(temperature=0.7)

    embeddings = DashScopeEmbeddings(
        model_name="text-embedding-v3",
        api_key=api_key,
    )

    vectorstore = QdrantVectorStoreFactory.create(
        collection_name="hvac_knowledge",
        embeddings=embeddings,
    )

    rag_chain = AdvancedRAGChain(
        vectorstore=vectorstore,
        llm=llm,
    )

    query = "中央空调系统的COP值一般是多少？"
    result = rag_chain.invoke(query, return_context=True)

    print(f"\n问题: {query}")
    print(f"\n回答:\n{result['answer']}")
    print(f"\n置信度: {result.get('confidence', 'N/A')}")


def example_02_agentic_rag():
    """示例2: Agentic RAG（带意图识别和工具路由）"""
    print("\n" + "=" * 60)
    print("示例2: Agentic RAG（意图识别+工具路由）")
    print("=" * 60)

    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        print("请设置 DASHSCOPE_API_KEY 环境变量")
        return

    llm = get_qwen_chat(temperature=0.7)

    embeddings = DashScopeEmbeddings(
        model_name="text-embedding-v3",
        api_key=api_key,
    )

    vectorstore = QdrantVectorStoreFactory.create(
        collection_name="hvac_knowledge",
        embeddings=embeddings,
    )

    tools = get_all_tools(
        vectorstore=vectorstore,
        llm=llm,
        historical_prices={
            "冷水机组": 500000,
            "冷却塔": 80000,
            "风机盘管": 3500,
        },
        supplier_whitelist=["格力", "美的", "麦克维尔", "开利"],
    )

    agent = AgenticRAGAgent(
        llm=llm,
        tools=tools,
        max_iterations=5,
        confidence_threshold=0.75,
    )

    query = "请帮我查询冷水机组的设计规范"
    result = agent.invoke(query)

    print(f"\n问题: {query}")
    print(f"\n回答:\n{result['answer']}")
    print(f"\n意图: {result.get('intent')}")
    print(f"置信度: {result.get('confidence')}")
    print(f"需人工审核: {result.get('needs_human_review')}")


def example_03_react_agent():
    """示例3: ReAct Agent（推理+行动）"""
    print("\n" + "=" * 60)
    print("示例3: ReAct Agent")
    print("=" * 60)

    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        print("请设置 DASHSCOPE_API_KEY 环境变量")
        return

    llm = get_qwen_chat(temperature=0.7)

    tools = get_all_tools(
        llm=llm,
        historical_prices={
            "冷水机组": 500000,
            "冷却塔": 80000,
        },
    )

    agent = ReActAgent(
        llm=llm,
        tools=tools,
        max_iterations=3,
    )

    query = "冷水机组的市场价格一般在什么范围？"
    result = agent.run(query)

    print(f"\n问题: {query}")
    print(f"\n回答:\n{result['answer']}")
    print(f"\n迭代次数: {result['iterations']}")


def example_04_conversational_rag():
    """示例4: 对话式RAG（多轮对话）"""
    print("\n" + "=" * 60)
    print("示例4: 对话式RAG")
    print("=" * 60)

    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        print("请设置 DASHSCOPE_API_KEY 环境变量")
        return

    llm = get_qwen_chat(temperature=0.7)

    embeddings = DashScopeEmbeddings(
        model_name="text-embedding-v3",
        api_key=api_key,
    )

    vectorstore = QdrantVectorStoreFactory.create(
        collection_name="hvac_knowledge",
        embeddings=embeddings,
    )

    conv_rag = ConversationalRAGChain(
        vectorstore=vectorstore,
        llm=llm,
    )

    queries = [
        "中央空调系统由哪些主要设备组成？",
        "冷水机组的作用是什么？",
        "冷却塔的选型需要考虑哪些因素？",
    ]

    for query in queries:
        print(f"\n用户: {query}")
        result = conv_rag.invoke(query)
        print(f"助手: {result['answer'][:200]}...")

    print("\n[对话历史已保存，可用于上下文理解]")


def example_05_document_processing():
    """示例5: 文档处理和入库"""
    print("\n" + "=" * 60)
    print("示例5: 文档处理和入库")
    print("=" * 60)

    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        print("请设置 DASHSCOPE_API_KEY 环境变量")
        return

    docs = load_and_process_documents(
        file_paths=[
            "data/hvac_design_guide.pdf",
            "data/chiller_manual.docx",
        ],
        chunk_size=512,
        chunk_overlap=100,
        document_type="技术文档",
    )

    print(f"\n成功处理文档块数: {len(docs)}")

    embeddings = DashScopeEmbeddings(
        model_name="text-embedding-v3",
        api_key=api_key,
    )

    vectorstore = QdrantVectorStore.from_documents(
        documents=docs,
        embeddings=embeddings,
        collection_name="hvac_knowledge",
    )

    print(f"\n已存入向量数据库")


def example_06_quote_validation():
    """示例6: 报价复核"""
    print("\n" + "=" * 60)
    print("示例6: 报价复核")
    print("=" * 60)

    from langchain_rag.tools.agent_tools import create_quote_validator

    validator = create_quote_validator(
        historical_prices={
            "冷水机组 500RT": 1800000,
            "冷却塔 500RT": 280000,
            "风机盘管 2HP": 3200,
        },
        supplier_whitelist=["格力", "美的", "麦克维尔"],
        material_cost_ratio=0.7,
        labor_cost_ratio=0.15,
        management_cost_ratio=0.15,
    )

    quote_text = """
    冷水机组 500RT: 1,850,000 元
    冷却塔 500RT: 295,000 元
    风机盘管 2HP: 10 台 × 3,500 元 = 35,000 元
    """

    result = validator._run(quote_text)

    print(f"\n报价复核结果:")
    print(f"总体通过: {'✅' if result['overall_passed'] else '❌'}")
    print(f"置信度: {result['confidence']}")
    print(f"复核项目数: {result['items_validated']}")

    for detail in result['details']:
        print(f"\n  项目: {detail['item']}")
        print(f"  单价: {detail['unit_price']}")
        print(f"  历史校验: {detail['historical_validation']['message']}")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("Agentic RAG 快速启动示例")
    print("=" * 60)

    examples = [
        ("基础RAG问答", example_01_basic_rag),
        ("Agentic RAG", example_02_agentic_rag),
        ("ReAct Agent", example_03_react_agent),
        ("对话式RAG", example_04_conversational_rag),
        ("文档处理入库", example_05_document_processing),
        ("报价复核", example_06_quote_validation),
    ]

    for i, (name, func) in enumerate(examples, 1):
        try:
            func()
        except Exception as e:
            print(f"\n示例{i}执行出错: {str(e)}")

    print("\n" + "=" * 60)
    print("示例执行完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
