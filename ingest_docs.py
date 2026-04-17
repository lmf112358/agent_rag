import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ingest_docs.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from langchain_core.documents import Document

from langchain_rag.document.processor import (
    DocumentProcessor,
    ChunkConfig,
    DocumentMetadata,
)
from langchain_rag.document.quality_checker import QualityChecker
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
    show_chunk_preview: bool = True,
) -> List[Document]:
    """
    递归加载 root_dir 下所有文档，切分并返回 Document 列表
    文件夹层级会自动作为元数据（Phase 1 增强版）

    Args:
        root_dir: 根目录（默认 "data"）
        chunk_size: 分块大小（默认从 config 读取）
        chunk_overlap: 分块重叠（默认从 config 读取）
        document_type: 文档类型标签
        show_chunk_preview: 是否显示切片预览

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
        msg = f"在 {root_dir}/ 下未找到文档文件"
        print(f"[警告] {msg}")
        logger.warning(msg)
        return []

    msg = f"共找到 {len(doc_files)} 个文档"
    print(f"[info] {msg}")
    logger.info(msg)

    all_docs = []
    skipped_files = []
    total_files = len(doc_files)

    for idx, file_path in enumerate(doc_files, 1):
        # 进度条
        progress = f"[{idx}/{total_files}]"
        msg = f"{progress} 处理: {file_path}"
        print(f"  {msg}")
        logger.info(msg)

        # 1. 质量检测
        quality_report = None
        try:
            quality_report = QualityChecker.check(str(file_path))
            if quality_report.quality_tag in ["UNSUPPORTED_FORMAT", "CORRUPTED", "ENCRYPTED"]:
                skip_msg = f"跳过 {quality_report.quality_tag}: {quality_report.issues}"
                print(f"    [跳过] {skip_msg}")
                logger.warning(f"{file_path}: {skip_msg}")
                skipped_files.append((file_path, quality_report))
                continue

            if quality_report.issues:
                warn_msg = f"{quality_report.quality_tag}: {quality_report.issues}"
                print(f"    [警告] {warn_msg}")
                logger.warning(f"{file_path}: {warn_msg}")
        except Exception as e:
            warn_msg = f"质量检测跳过: {e}"
            print(f"    [警告] {warn_msg}")
            logger.warning(f"{file_path}: {warn_msg}")

        # 2. 路径元数据提取（增强版）
        try:
            base_meta = DocumentMetadata.from_path_advanced(str(file_path), root_dir)
            logger.info(f"{file_path}: 提取元数据成功: {base_meta}")
        except Exception as e:
            try:
                base_meta = DocumentMetadata.from_file_path(str(file_path))
                # 降级到基础路径元数据
                folder_meta = extract_metadata_from_folder_structure(file_path, root_dir)
                base_meta.update(folder_meta)
                warn_msg = f"高级元数据提取失败，使用基础版: {e}"
                print(f"    [警告] {warn_msg}")
                logger.warning(f"{file_path}: {warn_msg}")
            except Exception:
                base_meta = {"source": str(file_path), "filename": file_path.name}

        # 3. 添加质量标签
        if quality_report:
            base_meta["quality_tag"] = quality_report.quality_tag
            base_meta["quality_score"] = quality_report.quality_score
            if quality_report.page_count:
                base_meta["page_count"] = quality_report.page_count

        # 4. 添加文档类型
        base_meta = DocumentMetadata.add_document_type(base_meta, document_type)

        # 5. 加载并切分文档
        try:
            docs = processor.load_document(str(file_path), base_meta)
            split_docs = processor.split_documents(docs)

            # 显示切片预览
            if show_chunk_preview and split_docs:
                preview_count = min(3, len(split_docs))
                print(f"    [info] 生成 {len(split_docs)} 个切片，前 {preview_count} 个预览:")
                logger.info(f"{file_path}: 生成 {len(split_docs)} 个切片")

                for i in range(preview_count):
                    chunk = split_docs[i]
                    preview_text = chunk.page_content[:150].replace("\n", " ")
                    print(f"      切片 {i+1}: [{chunk.metadata.get('chunk_type', 'text')}] {preview_text}...")
                    logger.debug(f"  切片 {i+1} 元数据: {chunk.metadata}")

            all_docs.extend(split_docs)
        except Exception as e:
            skip_msg = f"文档加载失败: {e}"
            print(f"    [跳过] {skip_msg}")
            logger.error(f"{file_path}: {skip_msg}")
            skipped_files.append((file_path, str(e)))
            continue

    if skipped_files:
        msg = f"共跳过 {len(skipped_files)} 个文件"
        print(f"\n[info] {msg}")
        logger.info(msg)

    msg = f"所有文档处理完成，共生成 {len(all_docs)} 个切片"
    print(f"[info] {msg}")
    logger.info(msg)

    return all_docs


def main():
    print("=" * 60)
    print("Agentic RAG - 递归文档解析与灌库")
    print("=" * 60)
    logger.info("=" * 60)
    logger.info("Agentic RAG - 递归文档解析与灌库")
    logger.info("=" * 60)

    # 1. 确保 data/ 目录存在（如果没有，创建示例结构）
    root_dir = "data"
    if not os.path.exists(root_dir):
        os.makedirs(root_dir)
        msg = f"创建示例目录结构: {root_dir}/"
        print(f"[info] {msg}")
        logger.info(msg)

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
        msg = "创建示例文档完成"
        print(f"[info] {msg}")
        logger.info(msg)

    # 2. 递归加载并切分文档
    step_msg = f"[1/4] 递归扫描并处理文档: {root_dir}/"
    print(f"\n{step_msg}")
    logger.info(step_msg)

    docs = load_and_process_documents_recursive(
        root_dir=root_dir,
        document_type="技术文档",
        show_chunk_preview=True,
    )
    if not docs:
        err_msg = "没有可处理的文档"
        print(f"[错误] {err_msg}")
        logger.error(err_msg)
        return

    info_msg = f"文档切分完成，共 {len(docs)} 个片段"
    print(f"\n[info] {info_msg}")
    logger.info(info_msg)

    # 3. 初始化 Embeddings 并获取实际维度
    step_msg = "[2/4] 初始化 Embedding 模型"
    print(f"\n{step_msg}")
    logger.info(step_msg)

    api_key = config.embedding.effective_api_key
    if not api_key:
        err_msg = "未设置 DASHSCOPE_API_KEY，请在 .env 中配置"
        print(f"[错误] {err_msg}")
        logger.error(err_msg)
        return

    embeddings = DashScopeEmbeddings(
        model_name=config.embedding.model_name,
        api_key=api_key,
    )

    # 获取实际 embedding 维度（先测试一下）
    logger.info("测试 Embedding 调用...")
    test_embedding = embeddings.embed_query("test")
    actual_dim = len(test_embedding)
    print(f"      模型: {config.embedding.model_name}")
    print(f"      实际维度: {actual_dim}")
    logger.info(f"Embedding 模型: {config.embedding.model_name}, 维度: {actual_dim}")

    # 4. 存入 Qdrant（先检查集合维度，不匹配则重建）
    collection_name = config.vectorstore.collection_name
    step_msg = f"[3/4] 向量化并写入 Qdrant 集合: {collection_name}"
    print(f"\n{step_msg}")
    logger.info(step_msg)

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
            warn_msg = f"现有集合维度 {existing_dim} 与实际维度 {actual_dim} 不匹配"
            print(f"      [警告] {warn_msg}")
            logger.warning(warn_msg)
            info_msg = "删除旧集合并重建..."
            print(f"      [info] {info_msg}")
            logger.info(info_msg)
            vectorstore.client.delete_collection(collection_name)
    except Exception:
        pass  # 集合不存在，没问题

    # 创建集合（如果需要）并添加文档
    logger.info("确保 Qdrant 集合存在...")
    vectorstore._create_collection_if_not_exists(actual_dim, config.vectorstore.distance)

    # 分批向量化并写入，显示进度
    batch_size = 50
    total_docs = len(docs)
    logger.info(f"开始向量化 {total_docs} 个文档片段，每批 {batch_size} 个...")
    print(f"      开始向量化 {total_docs} 个文档片段...")

    for i in range(0, total_docs, batch_size):
        batch_end = min(i + batch_size, total_docs)
        batch_docs = docs[i:batch_end]
        progress = f"[{batch_end}/{total_docs}]"

        # 显示进度
        print(f"      {progress} 向量化并写入批次 {i//batch_size + 1}...")
        logger.info(f"向量化批次 {i//batch_size + 1}: 文档 {i+1}-{batch_end}")

        # 写入当前批次
        vectorstore.add_documents(batch_docs, batch_size=batch_size)

    logger.info("向量化完成")
    print(f"      ✅ 向量化完成，共 {total_docs} 个片段")

    # 5. 验证
    step_msg = "[4/4] 验证入库结果"
    print(f"\n{step_msg}")
    logger.info(step_msg)

    try:
        info = vectorstore.get_collection_info()
        print(f"      集合信息: {info}")
        logger.info(f"集合信息: {info}")
    except Exception as e:
        warn_msg = f"获取集合信息失败: {e}"
        print(f"      [警告] {warn_msg}")
        logger.warning(warn_msg)

    print("\n" + "=" * 60)
    print("✅ 文档灌库完成！")
    print("=" * 60)
    print("\n提示: 文档已成功存入 Qdrant，你可以通过后端 API 进行检索测试。")
    logger.info("=" * 60)
    logger.info("文档灌库完成！")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
