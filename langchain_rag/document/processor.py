"""
文档处理模块
支持多种文档格式加载和智能分块策略
"""

import os
import re
from typing import List, Optional, Dict, Any, Callable, Union
from pathlib import Path
from langchain.schema import Document
from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
    TextSplitter,
    CharacterTextSplitter,
)
from langchain.document_loaders import (
    PyPDFLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredExcelLoader,
    UnstructuredPowerPointLoader,
    CSVLoader,
    TextLoader,
)
from langchain.document_loaders.base import BaseLoader


class ChunkConfig:
    """分块配置"""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 100,
        separators: Optional[List[str]] = None,
        length_function: Callable[[str], int] = len,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", "。", "；", " ", ""]
        self.length_function = length_function


class DocumentProcessor:
    """文档处理器"""

    LOADER_MAPPING: Dict[str, type] = {
        ".pdf": PyPDFLoader,
        ".docx": UnstructuredWordDocumentLoader,
        ".doc": UnstructuredWordDocumentLoader,
        ".xlsx": UnstructuredExcelLoader,
        ".xls": UnstructuredExcelLoader,
        ".pptx": UnstructuredPowerPointLoader,
        ".ppt": UnstructuredPowerPointLoader,
        ".csv": CSVLoader,
        ".txt": TextLoader,
        ".md": TextLoader,
    }

    def __init__(
        self,
        chunk_config: Optional[ChunkConfig] = None,
        extract_images: bool = False,
    ):
        self.chunk_config = chunk_config or ChunkConfig()
        self.extract_images = extract_images

    def get_loader(self, file_path: str) -> BaseLoader:
        """根据文件扩展名获取合适的加载器"""
        ext = Path(file_path).suffix.lower()

        if ext not in self.LOADER_MAPPING:
            raise ValueError(
                f"Unsupported file type: {ext}. "
                f"Supported types: {list(self.LOADER_MAPPING.keys())}"
            )

        loader_class = self.LOADER_MAPPING[ext]

        if ext in [".docx", ".doc"]:
            return loader_class(file_path, mode="elements")
        elif ext == ".pdf":
            return loader_class(file_path)
        elif ext in [".xlsx", ".xls"]:
            return loader_class(file_path)
        elif ext == ".csv":
            return loader_class(file_path, encoding="utf-8")
        else:
            return loader_class(file_path)

    def load_document(self, file_path: str, metadata: Optional[Dict[str, Any]] = None) -> List[Document]:
        """加载单个文档"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        loader = self.get_loader(file_path)
        docs = loader.load()

        if metadata:
            for doc in docs:
                doc.metadata.update(metadata)

        return docs

    def load_documents(
        self,
        directory: str,
        glob_pattern: str = "**/*",
        metadata_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
    ) -> List[Document]:
        """批量加载目录下的文档"""
        docs = []
        path = Path(directory)

        for file_path in path.glob(glob_pattern):
            if file_path.is_file():
                try:
                    file_metadata = {}
                    if metadata_fn:
                        file_metadata = metadata_fn(str(file_path))
                    docs.extend(self.load_document(str(file_path), file_metadata))
                except Exception as e:
                    print(f"Warning: Failed to load {file_path}: {str(e)}")

        return docs

    def split_documents(
        self,
        documents: List[Document],
        chunk_config: Optional[ChunkConfig] = None,
    ) -> List[Document]:
        """分割文档为块"""
        cfg = chunk_config or self.chunk_config

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=cfg.chunk_size,
            chunk_overlap=cfg.chunk_overlap,
            separators=cfg.separators,
            length_function=cfg.length_function,
            add_start_index=True,
        )

        return text_splitter.split_documents(documents)


class ChineseTextSplitter(RecursiveCharacterTextSplitter):
    """针对中文优化的文本分割器"""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 100,
        separators: Optional[List[str]] = None,
    ):
        if separators is None:
            separators = [
                "\n\n", "\n", "。", "；", "！", "？", "，", " ",
                "、", "）", "」", "'", "\"", "】", "]]",
            ]
        super().__init__(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            length_function=len,
            add_start_index=True,
        )

    def split_text(self, text: str) -> List[str]:
        """分割文本"""
        chunks = []
        for separator in self.separators:
            if separator == "":
                continue
            combined_separator = separator
            if len(chunks) > 0:
                last_chunk = chunks[-1]
                new_chunks = []
                for chunk in text.split(separator):
                    if new_chunks and chunk:
                        new_chunks[-1] = new_chunks[-1] + combined_separator + chunk
                    elif chunk:
                        new_chunks.append(chunk)
                chunks = new_chunks
            else:
                chunks = text.split(separator)

            if all(len(chunk) <= self.chunk_size for chunk in chunks):
                break

        if len(chunks) == 1:
            return self._safe_split(chunks[0])
        else:
            return [self._safe_split(chunk) for chunk in chunks if chunk]

    def _safe_split(self, text: str) -> str:
        """安全分割长文本"""
        if len(text) <= self.chunk_size:
            return text

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            if end < len(text):
                for sep in ["。", "；", "，", "、"]:
                    idx = text.rfind(sep, start, end)
                    if idx > start:
                        end = idx + 1
                        break
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end
        return "\n\n".join(chunks) if chunks else text


class MarkdownProcessor:
    """Markdown文档专用处理器"""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def process(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> List[Document]:
        """处理Markdown内容"""
        sections = self._split_by_headers(content)

        docs = []
        for section in sections:
            heading = section.get("heading", "")
            content_text = section.get("content", "").strip()

            if not content_text:
                continue

            chunk_size = self.chunk_size
            content_text = content_text.replace("\r\n", "\n").replace("\r", "\n")

            while len(content_text) > chunk_size:
                chunk = content_text[:chunk_size]
                last_break = max(
                    chunk.rfind("\n"),
                    chunk.rfind("。"),
                    chunk.rfind("；"),
                )
                if last_break > chunk_size // 2:
                    chunk = chunk[: last_break + 1]

                chunk_metadata = {"heading": heading} if heading else {}
                if metadata:
                    chunk_metadata.update(metadata)
                chunk_metadata["chunk_index"] = len(docs)

                docs.append(Document(page_content=chunk, metadata=chunk_metadata))
                content_text = content_text[len(chunk):]
            else:
                if content_text:
                    chunk_metadata = {"heading": heading} if heading else {}
                    if metadata:
                        chunk_metadata.update(metadata)

                    docs.append(Document(page_content=content_text, metadata=chunk_metadata))

        return docs

    def _split_by_headers(self, content: str) -> List[Dict[str, str]]:
        """按标题分割Markdown"""
        lines = content.split("\n")
        sections = []
        current_heading = ""
        current_content = []

        for line in lines:
            header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if header_match:
                if current_content:
                    sections.append({
                        "heading": current_heading,
                        "content": "\n".join(current_content),
                    })
                    current_content = []
                current_heading = header_match.group(2)
            else:
                current_content.append(line)

        if current_content:
            sections.append({
                "heading": current_heading,
                "content": "\n".join(current_content),
            })

        return sections


class DocumentMetadata:
    """文档元数据工具类"""

    @staticmethod
    def from_file_path(file_path: str) -> Dict[str, Any]:
        """从文件路径提取元数据"""
        path = Path(file_path)
        return {
            "source": str(path.absolute()),
            "filename": path.name,
            "file_extension": path.suffix,
            "file_size": os.path.getsize(file_path),
        }

    @staticmethod
    def add_document_type(
        metadata: Dict[str, Any],
        doc_type: str,
    ) -> Dict[str, Any]:
        """添加文档类型"""
        metadata["document_type"] = doc_type
        return metadata

    @staticmethod
    def add_classification(
        metadata: Dict[str, Any],
        classification: str,
    ) -> Dict[str, Any]:
        """添加分类标签"""
        metadata["classification"] = classification
        return metadata

    @staticmethod
    def add_project_info(
        metadata: Dict[str, Any],
        project_name: str,
        project_year: Optional[str] = None,
    ) -> Dict[str, Any]:
        """添加项目信息"""
        metadata["project_name"] = project_name
        if project_year:
            metadata["project_year"] = project_year
        return metadata


def load_and_process_documents(
    file_paths: List[str],
    chunk_size: int = 512,
    chunk_overlap: int = 100,
    document_type: Optional[str] = None,
    add_metadata: Optional[Dict[str, Any]] = None,
) -> List[Document]:
    """便捷函数：加载并处理文档"""
    processor = DocumentProcessor(
        chunk_config=ChunkConfig(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    )

    all_docs = []
    for file_path in file_paths:
        metadata = DocumentMetadata.from_file_path(file_path)
        if document_type:
            metadata = DocumentMetadata.add_document_type(metadata, document_type)
        if add_metadata:
            metadata.update(add_metadata)

        docs = processor.load_document(file_path, metadata)
        all_docs.extend(docs)

    return processor.split_documents(all_docs)
