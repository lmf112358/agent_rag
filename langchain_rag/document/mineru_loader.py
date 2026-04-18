"""
MinerU 文档加载器
基于 LangChain BaseLoader 接口，支持复杂 PDF 解析
"""
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

from langchain_core.documents import Document

from langchain_rag.document.mineru_client import MinerUClient, MinerUParseResult

logger = logging.getLogger(__name__)


class MinerULoader:
    """
    MinerU PDF 加载器

    特点：
    - 支持复杂版式 PDF 解析（合并单元格、跨页表格、公式等）
    - 输出 Markdown 格式，保留表格结构
    - 自动检测页码、标题层级
    """

    def __init__(
        self,
        file_path: str,
        client: Optional[MinerUClient] = None,
        enable_ocr: bool = False,
        enable_formula: bool = True,
        enable_table: bool = True,
        **kwargs: Any,
    ):
        """
        初始化 MinerU 加载器

        Args:
            file_path: PDF 文件路径
            client: MinerU 客户端实例（如果不传则自动创建）
            enable_ocr: 是否启用 OCR（默认 False，非扫描件不需要）
            enable_formula: 是否启用公式识别（默认 True）
            enable_table: 是否启用表格识别（默认 True）
        """
        self.file_path = file_path
        self.client = client
        self.enable_ocr = enable_ocr
        self.enable_formula = enable_formula
        self.enable_table = enable_table

        # 如果未传入 client，自动从配置创建
        if self.client is None:
            from langchain_rag.document.mineru_client import create_mineru_client_from_config
            self.client = create_mineru_client_from_config()

    def load(self) -> List[Document]:
        """
        加载并解析 PDF 文件

        Returns:
            Document 列表（按页面或章节分段）
        """
        path = Path(self.file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")

        if path.suffix.lower() != ".pdf":
            raise ValueError(f"MinerULoader only supports PDF files, got: {path.suffix}")

        # 如果 MinerU 未启用或无法连接，降级到普通 PDF 加载器
        if self.client is None:
            logger.warning(f"MinerU not enabled or configured, falling back to PyPDFLoader for: {path.name}")
            return self._fallback_load()

        # 检查服务健康状态
        if not self.client.health_check():
            logger.warning(f"MinerU service not available, falling back to PyPDFLoader for: {path.name}")
            return self._fallback_load()

        # 调用 MinerU 解析
        logger.info(f"Using MinerU to parse: {path.name}")
        result: MinerUParseResult = self.client.parse_pdf(
            file_path=str(path),
            output_format="markdown",
            enable_ocr=self.enable_ocr,
            enable_formula=self.enable_formula,
            enable_table=self.enable_table,
        )

        if not result.success:
            logger.error(f"MinerU parse failed for {path.name}: {result.error}")
            logger.info(f"Falling back to PyPDFLoader for: {path.name}")
            return self._fallback_load()

        # 解析成功，构建 Document
        logger.info(f"MinerU parse success: {path.name}, {result.page_count} pages, {result.table_count} tables")
        return self._create_documents_from_markdown(result.markdown, path.name, result)

    def _fallback_load(self) -> List[Document]:
        """降级到 PyPDFLoader"""
        from langchain_rag.document.processor import PyPDFLoader
        loader = PyPDFLoader(self.file_path)
        return loader.load()

    def _create_documents_from_markdown(
        self,
        markdown: str,
        source_name: str,
        result: MinerUParseResult,
    ) -> List[Document]:
        """
        从 MinerU 输出的 Markdown 创建 Document 列表

        策略：
        - 优先按 Markdown 标题分割（## 级别）
        - 如果单节内容过大，再按段落分割
        """
        import re

        docs: List[Document] = []

        # 基础元数据
        base_metadata = {
            "source": self.file_path,
            "source_name": source_name,
            "page_count": result.page_count,
            "table_count": result.table_count,
            "parse_time_seconds": result.parse_time_seconds,
            "parser": "mineru",
        }

        # 尝试按 Markdown 标题分割
        # 匹配 ## 或 ### 开头的标题
        heading_pattern = r'\n##\s+(.+?)\n'
        sections = re.split(heading_pattern, '\n' + markdown)

        if len(sections) <= 1:
            # 没有明显标题结构，整体作为一个文档
            docs.append(Document(
                page_content=markdown,
                metadata={
                    **base_metadata,
                    "section": "full_document",
                },
            ))
        else:
            # 按标题分割后的 sections 格式: [prefix, title1, content1, title2, content2, ...]
            # 第一个 section 可能是无标题前缀
            if sections[0].strip():
                docs.append(Document(
                    page_content=sections[0].strip(),
                    metadata={
                        **base_metadata,
                        "section": "prefix",
                    },
                ))

            # 处理 (title, content) 对
            for i in range(1, len(sections), 2):
                title = sections[i] if i < len(sections) else ""
                content = sections[i + 1] if i + 1 < len(sections) else ""

                section_content = f"## {title}\n\n{content}".strip()
                if section_content:
                    docs.append(Document(
                        page_content=section_content,
                        metadata={
                            **base_metadata,
                            "section_title": title.strip(),
                            "section_index": (i - 1) // 2,
                        },
                    ))

        logger.info(f"Created {len(docs)} documents from MinerU output")
        return docs


class MinerUMarkdownSplitter:
    """
    MinerU Markdown 专用分割器

    特点：
    - 保留 Markdown 表格完整性
    - 智能识别代码块、公式块
    - 支持按标题层级分割
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 100,
        preserve_tables: bool = True,
        preserve_code_blocks: bool = True,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.preserve_tables = preserve_tables
        self.preserve_code_blocks = preserve_code_blocks

    def split_text(self, text: str) -> List[str]:
        """分割 Markdown 文本"""
        if not self.preserve_tables:
            # 简单按长度分割
            return self._split_by_length(text)

        # 识别特殊块（表格、代码块）
        blocks = self._extract_blocks(text)

        # 合并块为 chunks
        return self._merge_blocks_to_chunks(blocks)

    def _extract_blocks(self, text: str) -> List[Dict[str, Any]]:
        """提取 Markdown 中的特殊块"""
        import re

        blocks = []
        remaining = text

        # 匹配表格块
        table_pattern = r'((?:^|\n)\|[^\n]+\|\n\|[-:| ]+\|\n(?:\|[^\n]+\|\n?)+)'

        while remaining:
            match = re.search(table_pattern, remaining)
            if not match:
                # 没有更多表格，剩余作为文本块
                if remaining.strip():
                    blocks.append({
                        "type": "text",
                        "content": remaining.strip(),
                        "length": len(remaining.strip()),
                    })
                break

            # 表格前的文本
            before = remaining[:match.start()]
            if before.strip():
                blocks.append({
                    "type": "text",
                    "content": before.strip(),
                    "length": len(before.strip()),
                })

            # 表格
            table_content = match.group(1).strip()
            blocks.append({
                "type": "table",
                "content": table_content,
                "length": len(table_content),
            })

            remaining = remaining[match.end():]

        return blocks

    def _merge_blocks_to_chunks(self, blocks: List[Dict[str, Any]]) -> List[str]:
        """将块合并为 chunks"""
        chunks = []
        current_chunk = []
        current_length = 0

        for block in blocks:
            block_content = block["content"]
            block_length = block["length"]

            if block["type"] == "table":
                # 表格优先保持完整
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_length = 0

                chunks.append(block_content)
                continue

            # 普通文本块
            if current_length + block_length > self.chunk_size and current_chunk:
                # 保存当前 chunk
                chunks.append("\n\n".join(current_chunk))

                # 开始新 chunk（带重叠）
                overlap_text = self._get_overlap_text(current_chunk)
                current_chunk = [overlap_text, block_content] if overlap_text else [block_content]
                current_length = sum(len(c) for c in current_chunk)
            else:
                current_chunk.append(block_content)
                current_length += block_length

        # 处理剩余的 chunk
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return [c for c in chunks if c.strip()]

    def _get_overlap_text(self, chunks: List[str]) -> str:
        """获取重叠部分的文本"""
        if not chunks:
            return ""

        total_text = "\n\n".join(chunks)
        overlap_size = min(self.chunk_overlap, len(total_text) // 2)

        if overlap_size <= 0:
            return ""

        return total_text[-overlap_size:]

    def _split_by_length(self, text: str) -> List[str]:
        """简单按长度分割文本"""
        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk)

            if end >= text_len:
                break

            start = max(end - self.chunk_overlap, start + 1)

        return chunks
