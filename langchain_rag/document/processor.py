"""
文档处理模块
支持多种文档格式加载和智能分块策略
"""

import os
import re
from typing import List, Optional, Dict, Any, Callable
from pathlib import Path
from langchain_core.documents import Document


class BaseLoader:
    """基础文档加载器"""

    def load(self) -> List[Document]:
        raise NotImplementedError


class TextLoader(BaseLoader):
    """文本加载器（内置，无第三方依赖）"""

    def __init__(self, file_path: str, encoding: str = "utf-8", *args, **kwargs):
        self.file_path = file_path
        self.encoding = encoding

    def load(self) -> List[Document]:
        with open(self.file_path, "r", encoding=self.encoding, errors="ignore") as file:
            content = file.read()
        return [Document(page_content=content, metadata={"source": self.file_path})]


class CSVLoader(BaseLoader):
    """CSV加载器（内置，无第三方依赖）"""

    def __init__(self, file_path: str, encoding: str = "utf-8", *args, **kwargs):
        self.file_path = file_path
        self.encoding = encoding

    def load(self) -> List[Document]:
        import csv

        rows: List[str] = []
        with open(self.file_path, "r", encoding=self.encoding, errors="ignore", newline="") as file:
            reader = csv.reader(file)
            for row in reader:
                rows.append(",".join(row))

        return [Document(page_content="\n".join(rows), metadata={"source": self.file_path})]


class PyPDFLoader(BaseLoader):
    """PDF 加载器（使用 pypdf）"""

    def __init__(self, file_path: str, *args, **kwargs):
        self.file_path = file_path

    def load(self) -> List[Document]:
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ImportError("pypdf is required. Install it: pip install pypdf")

        reader = PdfReader(self.file_path)
        docs = []
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                metadata = {
                    "source": self.file_path,
                    "page": page_num + 1,
                }
                docs.append(Document(page_content=text, metadata=metadata))
        return docs


class UnstructuredWordDocumentLoader(BaseLoader):
    """DOCX 加载器（使用 python-docx）"""

    def __init__(self, file_path: str, *args, **kwargs):
        self.file_path = file_path

    def load(self) -> List[Document]:
        try:
            from docx import Document as DocxDocument
        except ImportError:
            raise ImportError("python-docx is required. Install it: pip install python-docx")

        doc = DocxDocument(self.file_path)
        full_text = []
        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text)

        text = "\n".join(full_text)
        if not text.strip():
            return []

        return [Document(page_content=text, metadata={"source": self.file_path})]


class UnstructuredExcelLoader(BaseLoader):
    """Excel 加载器（可选，提示安装）"""

    def __init__(self, file_path: str, *args, **kwargs):
        self.file_path = file_path

    def load(self) -> List[Document]:
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for Excel. Install it: pip install pandas")

        df = pd.read_excel(self.file_path)
        text = df.to_csv(sep="\t", na_rep="")
        return [Document(page_content=text, metadata={"source": self.file_path})]


class UnstructuredPowerPointLoader(BaseLoader):
    """PPT 加载器（可选，提示安装）"""

    def __init__(self, file_path: str, *args, **kwargs):
        self.file_path = file_path

    def load(self) -> List[Document]:
        try:
            from pptx import Presentation
        except ImportError:
            raise ImportError("python-pptx is required for PowerPoint. Install it: pip install python-pptx")

        prs = Presentation(self.file_path)
        texts = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    texts.append(shape.text)

        text = "\n".join(texts)
        if not text.strip():
            return []

        return [Document(page_content=text, metadata={"source": self.file_path})]


class RecursiveCharacterTextSplitter:
    """简化递归文本分割器（无 langchain-text-splitters 依赖）"""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 100,
        separators: Optional[List[str]] = None,
        length_function: Callable[[str], int] = len,
        add_start_index: bool = False,
        **kwargs,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", " ", ""]
        self.length_function = length_function
        self.add_start_index = add_start_index

    def split_text(self, text: str) -> List[str]:
        if not text:
            return []

        chunks: List[str] = []
        start = 0
        total_len = len(text)

        while start < total_len:
            max_end = min(start + self.chunk_size, total_len)
            end = max_end

            if max_end < total_len:
                window = text[start:max_end]
                for sep in self.separators:
                    if not sep:
                        continue
                    idx = window.rfind(sep)
                    if idx > 0:
                        end = start + idx + len(sep)
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end >= total_len:
                break

            start = max(end - self.chunk_overlap, start + 1)

        return chunks

    def split_documents(self, documents: List[Document]) -> List[Document]:
        split_docs: List[Document] = []

        for doc in documents:
            chunks = self.split_text(doc.page_content)
            cursor = 0

            for chunk in chunks:
                metadata = dict(doc.metadata) if doc.metadata else {}
                if self.add_start_index:
                    idx = doc.page_content.find(chunk, cursor)
                    if idx < 0:
                        idx = cursor
                    metadata["start_index"] = idx
                    cursor = idx + len(chunk)

                split_docs.append(Document(page_content=chunk, metadata=metadata))

        return split_docs


class CharacterTextSplitter(RecursiveCharacterTextSplitter):
    """兼容占位：与递归分割器保持一致"""


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
        # 委托给父类的递归分割逻辑，仅在需要时对超长块做中文友好二次切割
        parent_chunks = super().split_text(text)
        result: List[str] = []
        for chunk in parent_chunks:
            if len(chunk) <= self.chunk_size:
                result.append(chunk)
            else:
                result.extend(self._safe_split_to_list(chunk))
        return result

    def _safe_split_to_list(self, text: str) -> List[str]:
        """将超长文本按中文标点安全切割为若干块"""
        if len(text) <= self.chunk_size:
            return [text]

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
        return chunks if chunks else [text]


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
