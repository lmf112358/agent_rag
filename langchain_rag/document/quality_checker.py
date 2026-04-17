"""
质量检测模块
"""
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Literal
from pathlib import Path

QualityTag = Literal[
    "CLEAN",
    "SCANNED",
    "CORRUPTED",
    "ENCRYPTED",
    "GARBAGE_ENCODING",
    "UNSUPPORTED_FORMAT",
]


@dataclass
class QualityReport:
    quality_tag: QualityTag
    quality_score: float
    issues: List[str]
    page_count: Optional[int] = None
    text_layer_present: bool = True


# 不支持的格式黑名单
UNSUPPORTED_EXTENSIONS = {".dwg", ".lr", ".hsdb", ".hec", ".dxf"}


class QualityChecker:
    """文档质量检测器"""

    @staticmethod
    def check(file_path: str) -> QualityReport:
        """
        检测文档质量，返回 QualityReport
        """
        path = Path(file_path)
        ext = path.suffix.lower()

        # 1. 格式黑名单检查
        if ext in UNSUPPORTED_EXTENSIONS:
            return QualityReport(
                quality_tag="UNSUPPORTED_FORMAT",
                quality_score=0.0,
                issues=[f"Unsupported format: {ext}"],
            )

        # 2. 文件存在性检查
        if not path.exists():
            return QualityReport(
                quality_tag="CORRUPTED",
                quality_score=0.0,
                issues=["File not found"],
            )

        # 3. PDF 专项检查
        if ext == ".pdf":
            return QualityChecker._check_pdf(file_path)

        # 4. Word/Excel 专项检查
        if ext in [".docx", ".doc", ".xlsx", ".xls"]:
            return QualityChecker._check_office(file_path)

        # 5. 文本文件检查
        if ext in [".txt", ".md", ".csv"]:
            return QualityChecker._check_text(file_path)

        # 默认通过
        return QualityReport(
            quality_tag="CLEAN",
            quality_score=1.0,
            issues=[],
        )

    @staticmethod
    def _check_pdf(file_path: str) -> QualityReport:
        """PDF 专项检查"""
        issues = []
        page_count = 0
        total_chars = 0
        text_layer_present = True

        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)

            # 检查加密
            if reader.is_encrypted:
                return QualityReport(
                    quality_tag="ENCRYPTED",
                    quality_score=0.0,
                    issues=["PDF is encrypted"],
                )

            page_count = len(reader.pages)
            char_counts = []

            for page in reader.pages:
                text = page.extract_text() or ""
                char_counts.append(len(text))
                total_chars += len(text)

            avg_chars_per_page = total_chars / page_count if page_count > 0 else 0

            # 扫描件检测：页面平均字符数 < 50
            if avg_chars_per_page < 50:
                issues.append(f"Low text density: {avg_chars_per_page:.1f} chars/page (likely scanned)")
                text_layer_present = False

            # 乱码检测
            sample_text = ""
            for page in reader.pages[:3]:
                sample_text += page.extract_text() or ""
                if len(sample_text) > 500:
                    break

            garbage_result = QualityChecker.check_garbage_text(sample_text)
            if garbage_result:
                issues.append(garbage_result)

            # 评分
            if issues:
                quality_tag = "SCANNED" if not text_layer_present else "GARBAGE_ENCODING" if garbage_result else "CLEAN"
                quality_score = 0.5 if text_layer_present else 0.2
            else:
                quality_tag = "CLEAN"
                quality_score = 1.0

            return QualityReport(
                quality_tag=quality_tag,
                quality_score=quality_score,
                issues=issues,
                page_count=page_count,
                text_layer_present=text_layer_present,
            )

        except Exception as e:
            return QualityReport(
                quality_tag="CORRUPTED",
                quality_score=0.0,
                issues=[f"Failed to read PDF: {str(e)}"],
            )

    @staticmethod
    def _check_office(file_path: str) -> QualityReport:
        """Office 文件检查"""
        try:
            ext = Path(file_path).suffix.lower()
            if ext in [".docx", ".doc"]:
                from docx import Document as DocxDocument
                doc = DocxDocument(file_path)
                # 简单检查：至少有一段
                if len(doc.paragraphs) == 0:
                    return QualityReport(
                        quality_tag="SCANNED",
                        quality_score=0.3,
                        issues=["No text found in document"],
                    )
            return QualityReport(
                quality_tag="CLEAN",
                quality_score=1.0,
                issues=[],
            )
        except Exception as e:
            return QualityReport(
                quality_tag="CORRUPTED",
                quality_score=0.0,
                issues=[f"Failed to read office file: {str(e)}"],
            )

    @staticmethod
    def _check_text(file_path: str) -> QualityReport:
        """文本文件检查"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read(1000)
            garbage_result = QualityChecker.check_garbage_text(text)
            if garbage_result:
                return QualityReport(
                    quality_tag="GARBAGE_ENCODING",
                    quality_score=0.5,
                    issues=[garbage_result],
                )
            return QualityReport(
                quality_tag="CLEAN",
                quality_score=1.0,
                issues=[],
            )
        except UnicodeDecodeError:
            return QualityReport(
                quality_tag="GARBAGE_ENCODING",
                quality_score=0.3,
                issues=["Unicode decode error"],
            )
        except Exception as e:
            return QualityReport(
                quality_tag="CORRUPTED",
                quality_score=0.0,
                issues=[f"Failed to read text file: {str(e)}"],
            )

    @staticmethod
    def check_garbage_text(text_sample: str) -> Optional[str]:
        """检测乱码文本"""
        if not text_sample or len(text_sample) < 100:
            return None

        # 中文字符比例检测
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text_sample))
        total_chars = len(text_sample)
        ratio = chinese_chars / total_chars

        if ratio < 0.3 and total_chars > 100:
            return f"Low Chinese ratio: {ratio:.1%} (expected >30% for Chinese docs)"

        # 乱码字符检测
        garbage_patterns = ['�', '��', '\x00', '\ufffd']
        if any(p in text_sample for p in garbage_patterns):
            return "Garbage characters detected (� etc.)"

        return None
