"""
文档处理模块测试
"""
import pytest
from pathlib import Path
from langchain_core.documents import Document

from langchain_rag.document.processor import (
    TextLoader,
    CSVLoader,
    RecursiveCharacterTextSplitter,
    ChineseTextSplitter,
    ChunkConfig,
    DocumentProcessor,
)


class TestTextLoader:
    """测试文本加载器"""

    def test_load_txt_file(self, tmp_path):
        """测试加载普通文本文件"""
        file_path = tmp_path / "test.txt"
        file_path.write_text("测试内容\n第二行内容", encoding="utf-8")

        loader = TextLoader(str(file_path))
        docs = loader.load()

        assert len(docs) == 1
        assert "测试内容" in docs[0].page_content
        assert docs[0].metadata["source"] == str(file_path)

    def test_load_with_metadata(self, tmp_path):
        """测试加载后元数据处理"""
        file_path = tmp_path / "test.txt"
        file_path.write_text("测试内容", encoding="utf-8")

        loader = TextLoader(str(file_path))
        docs = loader.load()

        assert "source" in docs[0].metadata


class TestRecursiveCharacterTextSplitter:
    """测试递归文本分割器"""

    def test_split_basic_text(self):
        """测试基本文本分割"""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=20,
            chunk_overlap=5,
        )
        text = "这是一段较长的中文文本，用于测试分块功能是否正常工作。"

        chunks = splitter.split_text(text)

        assert len(chunks) > 0
        for chunk in chunks:
            assert len(chunk) <= 25  # 允许少量超出

    def test_split_documents(self, sample_documents):
        """测试分割文档列表"""
        splitter = RecursiveCharacterTextSplitter(chunk_size=50)
        split_docs = splitter.split_documents(sample_documents)

        assert len(split_docs) >= len(sample_documents)
        for doc in split_docs:
            assert isinstance(doc, Document)
            assert "source" in doc.metadata


class TestChineseTextSplitter:
    """测试中文优化分割器"""

    def test_split_chinese_with_punctuation(self):
        """测试按中文标点分割"""
        splitter = ChineseTextSplitter(chunk_size=30)
        text = "这是第一句。这是第二句？这是第三句！这是第四句。"

        chunks = splitter.split_text(text)

        assert len(chunks) > 0
        # 确保分割点尽量在标点后
        for chunk in chunks:
            if len(chunk) < len(text):
                assert any(p in chunk[-1] for p in ["。", "！", "？"])


class TestDocumentProcessor:
    """测试文档处理器"""

    def test_get_loader_for_txt(self):
        """测试获取 TXT 加载器"""
        processor = DocumentProcessor()
        loader = processor.get_loader("test.txt")

        assert isinstance(loader, TextLoader)

    def test_get_loader_for_csv(self):
        """测试获取 CSV 加载器"""
        processor = DocumentProcessor()
        loader = processor.get_loader("test.csv")

        assert isinstance(loader, CSVLoader)

    def test_split_with_custom_config(self, sample_documents):
        """测试使用自定义配置分块"""
        config = ChunkConfig(chunk_size=100, chunk_overlap=20)
        processor = DocumentProcessor(chunk_config=config)

        split_docs = processor.split_documents(sample_documents)

        assert len(split_docs) >= len(sample_documents)
