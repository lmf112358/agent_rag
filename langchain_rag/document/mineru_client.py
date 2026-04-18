"""
MinerU 文档解析客户端封装
支持通过 HTTP REST API 调用 MinerU 进行复杂 PDF 解析
"""
import os
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass
class MinerUParseResult:
    """MinerU 解析结果"""
    success: bool
    markdown: Optional[str] = None
    raw_json: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    parse_time_seconds: float = 0.0
    page_count: int = 0
    table_count: int = 0


class MinerUClient:
    """MinerU HTTP API 客户端"""

    def __init__(
        self,
        api_base: str = "http://localhost:8008",
        api_key: str = "",
        timeout: int = 300,
    ):
        """
        初始化 MinerU 客户端

        Args:
            api_base: MinerU API 服务地址
            api_key: API 密钥（如需要）
            timeout: 请求超时时间（秒）
        """
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"X-API-Key": api_key})

    def health_check(self) -> bool:
        """
        检查 MinerU 服务是否可用

        Returns:
            服务是否健康
        """
        try:
            response = self.session.get(
                f"{self.api_base}/health",
                timeout=10,
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"MinerU health check failed: {e}")
            return False

    def parse_pdf(
        self,
        file_path: str,
        output_format: str = "markdown",
        enable_ocr: bool = False,
        enable_formula: bool = True,
        enable_table: bool = True,
    ) -> MinerUParseResult:
        """
        解析 PDF 文件

        Args:
            file_path: PDF 文件路径
            output_format: 输出格式 ("markdown" 或 "json")
            enable_ocr: 是否启用 OCR
            enable_formula: 是否启用公式识别
            enable_table: 是否启用表格识别

        Returns:
            MinerUParseResult 解析结果
        """
        start_time = time.time()
        path = Path(file_path)

        if not path.exists():
            return MinerUParseResult(
                success=False,
                error=f"File not found: {file_path}",
            )

        if path.suffix.lower() != ".pdf":
            return MinerUParseResult(
                success=False,
                error=f"Only PDF files are supported, got: {path.suffix}",
            )

        try:
            logger.info(f"Calling MinerU to parse: {path.name}")

            # 准备请求参数
            params = {
                "output_format": output_format,
                "enable_ocr": enable_ocr,
                "enable_formula": enable_formula,
                "enable_table": enable_table,
            }

            # 上传文件并调用解析
            with open(path, "rb") as f:
                files = {"file": (path.name, f, "application/pdf")}
                response = self.session.post(
                    f"{self.api_base}/parse",
                    files=files,
                    data=params,
                    timeout=self.timeout,
                )

            response.raise_for_status()
            result_data = response.json()

            parse_time = time.time() - start_time
            logger.info(f"MinerU parse completed in {parse_time:.1f}s")

            # 构建结果
            result = MinerUParseResult(
                success=True,
                parse_time_seconds=parse_time,
                page_count=result_data.get("page_count", 0),
                table_count=result_data.get("table_count", 0),
            )

            if output_format == "markdown":
                result.markdown = result_data.get("markdown", "")
            else:
                result.raw_json = result_data.get("data", {})

            return result

        except requests.exceptions.Timeout:
            error_msg = f"MinerU parse timeout after {self.timeout}s"
            logger.error(error_msg)
            return MinerUParseResult(
                success=False,
                error=error_msg,
                parse_time_seconds=time.time() - start_time,
            )
        except requests.exceptions.ConnectionError:
            error_msg = f"MinerU connection failed to {self.api_base}"
            logger.error(error_msg)
            return MinerUParseResult(
                success=False,
                error=error_msg,
                parse_time_seconds=time.time() - start_time,
            )
        except Exception as e:
            error_msg = f"MinerU parse failed: {str(e)}"
            logger.error(error_msg)
            return MinerUParseResult(
                success=False,
                error=error_msg,
                parse_time_seconds=time.time() - start_time,
            )

    def parse_pdf_to_markdown(
        self,
        file_path: str,
        enable_ocr: bool = False,
    ) -> Optional[str]:
        """
        快捷方法：解析 PDF 并返回 Markdown

        Args:
            file_path: PDF 文件路径
            enable_ocr: 是否启用 OCR

        Returns:
            Markdown 字符串，失败返回 None
        """
        result = self.parse_pdf(
            file_path=file_path,
            output_format="markdown",
            enable_ocr=enable_ocr,
            enable_formula=True,
            enable_table=True,
        )
        if result.success and result.markdown:
            return result.markdown
        return None


# 工厂函数
def create_mineru_client_from_config() -> Optional[MinerUClient]:
    """
    从配置创建 MinerU 客户端

    Returns:
        MinerUClient 实例，如果未启用则返回 None
    """
    from langchain_rag.config.settings import config

    if not config.mineru.enabled:
        logger.debug("MinerU is disabled in config")
        return None

    return MinerUClient(
        api_base=config.mineru.api_base,
        api_key=config.mineru.api_key,
        timeout=config.mineru.timeout,
    )
