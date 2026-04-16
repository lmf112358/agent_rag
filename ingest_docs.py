import os
import sys
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_core.documents import Document

from langchain_rag.document.processor import (
    DocumentProcessor,
    ChunkConfig,
    DocumentMetadata,
)
from langchain_rag.vectorstore.qdrant import QdrantVectorStore, DashScopeEmbeddings
from langchain_rag.config.settings import config


def find_all_documents(
    root_dir: str,
    supported_extensions: List[str] = None,
) -> List[Path]:
    """
    递归查找 root_dir 下所有支持的文档文件

    Args:
        root_dir: 根目录（如 "data"）
        supported_extensions: 支持的扩展名列表（默认: .pdf/.docx/.doc/.txt/.md/.csv）

    Returns:
        Path 对象列表
    """
    if supported_extensions is None:
        supported_extensions = [
            ".pdf", ".docx", ".doc", ".txt", ".md", ".csv",
            ".xlsx", ".xls", ".pptx", ".ppt",
        ]

    root = Path(root_dir)
    if not root.exists():
        return []

    doc_files = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in supported_extensions:
            doc_files.append(path)

    return sorted(doc_files)


def extract_metadata_from_folder_structure(
    file_path: Path,
    root_dir: str,
) -> Dict[str, Any]:
    """
    从文件夹路径结构中提取元数据（如分类、子分类等）

    示例:
        data/技术规范/中央空调/设计手册.pdf
        -> {
            "category": "技术规范",
            "subcategory": "中央空调",
            "folder_path": "技术规范/中央空调",
            ...
        }

    Args:
        file_path: 文件完整 Path
        root_dir: 根目录（用于计算相对路径）

    Returns:
        包含文件夹层级信息的元数据字典
    """
    root = Path(root_dir)
    rel_path = file_path.relative_to(root)
    parts = list(rel_path.parts[:-1])  # 去掉文件名

    metadata = {
        "folder_path": "/".join(parts) if parts else "",
    }

    # 按层级命名: category / subcategory / subsubcategory...
    level_names = ["category", "subcategory", "subsubcategory", "subsubsubcategory"]
    for i, part in enumerate(parts):
        if i < len(level_names):
            metadata[level_names[i]] = part

    return metadata


def load_and_process_documents_recursive(
    root_dir: str = "data",
    chunk_size: int = None,
    chunk_overlap: int = None,
    document_type: str = "技术文档",
) -> List[Document]:
    """
    递归加载 root_dir 下所有文档，切分并返回 Document 列表
    文件夹层级会自动作为元数据

    Args:
        root_dir: 根目录（默认 "data"）
        chunk_size: 分块大小（默认从 config 读取）
        chunk_overlap: 分块重叠（默认从 config 读取）
        document_type: 文档类型标签

    Returns:
        切分后的 Document 列表
    """
    chunk_size = chunk_size or config.rag.chunk_size
    chunk_overlap = chunk_overlap or config.rag.chunk_overlap

    processor = DocumentProcessor(
        chunk_config=ChunkConfig(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    )

    doc_files = find_all_documents(root_dir)
    if not doc_files:
        print(f"[警告] 在 {root_dir}/ 下未找到文档文件")
        return []

    print(f"[info] 共找到 {len(doc_files)} 个文档")

    all_docs = []
    for file_path in doc_files:
        print(f"  - 处理: {file_path}")

        # 1. 从文件路径提取基础元数据
        try:
            base_meta = DocumentMetadata.from_file_path(str(file_path))
        except Exception:
            base_meta = {"source": str(file_path), "filename": file_path.name}

        # 2. 从文件夹层级提取元数据（category/subcategory...）
        folder_meta = extract_metadata_from_folder_structure(file_path, root_dir)
        base_meta.update(folder_meta)

        # 3. 添加文档类型
        base_meta = DocumentMetadata.add_document_type(base_meta, document_type)

        # 4. 加载并切分文档
        try:
            docs = processor.load_document(str(file_path), base_meta)
            split_docs = processor.split_documents(docs)
            all_docs.extend(split_docs)
        except Exception as e:
            print(f"    [跳过] 处理失败: {e}")
            continue

    return all_docs


def main():
    print("=" * 60)
    print("Agentic RAG - 递归文档解析与灌库")
    print("=" * 60)

    # 1. 确保 data/ 目录存在（如果没有，创建示例结构）
    root_dir = "data"
    if not os.path.exists(root_dir):
        os.makedirs(root_dir)
        print(f"[info] 创建示例目录结构: {root_dir}/")

        # 创建示例文件夹结构
        example_folders = [
            "data/技术规范/中央空调",
            "data/技术规范/冷水机组",
            "data/操作手册/维护指南",
            "data/报价模板",
        ]
        for folder in example_folders:
            os.makedirs(folder, exist_ok=True)

        # 创建示例文件
        example_files = [
            ("data/技术规范/中央空调/设计参数.txt", """
中央空调系统由冷水机组、冷却塔、水泵、风机盘管、空气处理机组等设备组成。
冷水机组的作用是制取冷冻水，通过制冷剂在蒸发器内吸热来降低水温。
COP（能效比）是指制冷量与输入功率的比值，一般螺杆式冷水机组的COP在5.0-6.0左右。
"""),
            ("data/技术规范/冷水机组/选型标准.txt", """
冷水机组选型需考虑：制冷量、COP、冷冻水进出温度、冷却水进出温度、噪声、振动、占地面积等。
冷冻水进出水温度通常为 7℃/12℃，冷却水进出水温度通常为 32℃/37℃。
"""),
            ("data/操作手册/维护指南/日常巡检.txt", """
日常巡检项目：
1. 检查冷水机组运行电流、电压
2. 检查冷冻水、冷却水流量与温度
3. 检查冷却塔风机、水泵运行状态
4. 记录制冷剂高低压压力
"""),
            ("data/报价模板/设备清单模板.txt", """
典型设备清单：
- 冷水机组 500RT × 2台
- 冷却塔 500RT × 2台
- 冷冻水泵 × 3台
- 冷却水泵 × 3台
- 风机盘管若干
"""),
        ]
        for file_path, content in example_files:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content.strip())
        print(f"[info] 创建示例文档完成")

    # 2. 递归加载并切分文档
    print(f"\n[1/4] 递归扫描并处理文档: {root_dir}/")
    docs = load_and_process_documents_recursive(
        root_dir=root_dir,
        document_type="技术文档",
    )
    if not docs:
        print("[错误] 没有可处理的文档")
        return

    print(f"\n[info] 文档切分完成，共 {len(docs)} 个片段")

    # 3. 初始化 Embeddings 并获取实际维度
    print("\n[2/4] 初始化 Embedding 模型")
    api_key = config.embedding.effective_api_key
    if not api_key:
        print("[错误] 未设置 DASHSCOPE_API_KEY，请在 .env 中配置")
        return

    embeddings = DashScopeEmbeddings(
        model_name=config.embedding.model_name,
        api_key=api_key,
    )

    # 获取实际 embedding 维度（先测试一下）
    test_embedding = embeddings.embed_query("test")
    actual_dim = len(test_embedding)
    print(f"      模型: {config.embedding.model_name}")
    print(f"      实际维度: {actual_dim}")

    # 4. 存入 Qdrant（先检查集合维度，不匹配则重建）
    collection_name = config.vectorstore.collection_name
    print(f"\n[3/4] 向量化并写入 Qdrant 集合: {collection_name}")

    # 先创建 vectorstore 实例并检查/重建集合
    vectorstore = QdrantVectorStore(
        host=config.vectorstore.host,
        port=config.vectorstore.port,
        collection_name=collection_name,
        vector_dim=actual_dim,
        distance=config.vectorstore.distance,
        api_key=config.vectorstore.api_key,
        embeddings=embeddings,
    )

    # 检查现有集合维度是否匹配
    try:
        info = vectorstore.client.get_collection(collection_name)
        existing_dim = info.config.params.vectors.size
        if existing_dim != actual_dim:
            print(f"      [警告] 现有集合维度 {existing_dim} 与实际维度 {actual_dim} 不匹配")
            print(f"      [info] 删除旧集合并重建...")
            vectorstore.client.delete_collection(collection_name)
    except Exception:
        pass  # 集合不存在，没问题

    # 创建集合（如果需要）并添加文档
    vectorstore._create_collection_if_not_exists(actual_dim, config.vectorstore.distance)
    vectorstore.add_documents(docs)

    # 5. 验证
    print("\n[4/4] 验证入库结果")
    try:
        info = vectorstore.get_collection_info()
        print(f"      集合信息: {info}")
    except Exception as e:
        print(f"      [警告] 获取集合信息失败: {e}")

    print("\n" + "=" * 60)
    print("✅ 文档灌库完成！")
    print("=" * 60)
    print("\n提示: 文档已成功存入 Qdrant，你可以通过后端 API 进行检索测试。")


if __name__ == "__main__":
    main()
