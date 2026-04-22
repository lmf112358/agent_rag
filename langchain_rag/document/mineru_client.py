"""
MinerU 文档解析客户端封装
支持通过 HTTP REST API 调用 MinerU 进行复杂 PDF 解析

支持两种模式：
1. 本地API模式：直接POST /parse（旧版）
2. 云端官方API模式：使用官方 v4 接口（新版）
   - 已确认：申请上传链接、PUT 上传
   - 待补全文档：batch_id 对应的结果查询接口
"""
import os
import time
import logging
import zipfile
import io
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, TypeVar
from dataclasses import dataclass
from functools import wraps

import requests

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_on_failure(
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple = (requests.exceptions.RequestException,),
):
    """
    重试装饰器：指数退避重试机制

    Args:
        max_retries: 最大重试次数
        base_delay: 初始延迟（秒）
        max_delay: 最大延迟（秒）
        backoff_factor: 退避因子
        retryable_exceptions: 可重试的异常类型
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt >= max_retries:
                        logger.error(f"Final attempt {attempt + 1} failed, no more retries")
                        raise

                    # 计算延迟：指数退避 + 随机抖动
                    delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                    # 添加±10%的随机抖动避免雪崩
                    jitter = delay * 0.1 * (2 * (os.urandom(1)[0] / 255 - 0.5))
                    delay_with_jitter = max(0.5, delay + jitter)

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                        f"Retrying in {delay_with_jitter:.1f}s..."
                    )
                    time.sleep(delay_with_jitter)

            raise last_exception  # type: ignore
        return wrapper
    return decorator


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
        model_version: str = "vlm",
        poll_interval: int = 5,
        max_polls: int = 60,
    ):
        """
        初始化 MinerU 客户端

        Args:
            api_base: MinerU API 服务地址
            api_key: API 密钥（云端API必需，格式：Bearer Token）
            timeout: 请求超时时间（秒）
            model_version: 模型版本 (pipeline/vlm/MinerU-HTML)，默认vlm
            poll_interval: 轮询间隔（秒），默认5
            max_polls: 最大轮询次数，默认60
        """
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.model_version = model_version
        self.poll_interval = poll_interval
        self.max_polls = max_polls

        # 判断是否为云端API（有api_key则认为是云端）
        self.is_cloud_api = bool(api_key)

        self.session = requests.Session()
        if api_key:
            # 云端API使用 Authorization: Bearer {token}
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})

    @retry_on_failure(max_retries=2, base_delay=1.0)
    def health_check(self) -> bool:
        """
        检查 MinerU 服务是否可用

        Returns:
            服务是否健康
        """
        if self.is_cloud_api:
            # 云端API通过检查API Key是否存在来判断
            return bool(self.api_key)
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

            if self.is_cloud_api:
                # 云端官方API（异步流程）
                return self._parse_cloud_api_official(
                    path=path,
                    output_format=output_format,
                    enable_ocr=enable_ocr,
                    enable_formula=enable_formula,
                    enable_table=enable_table,
                    start_time=start_time,
                )
            else:
                # 本地API（同步流程）
                return self._parse_local_api(
                    path=path,
                    output_format=output_format,
                    enable_ocr=enable_ocr,
                    enable_formula=enable_formula,
                    enable_table=enable_table,
                    start_time=start_time,
                )

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
            import traceback
            logger.error(traceback.format_exc())
            return MinerUParseResult(
                success=False,
                error=error_msg,
                parse_time_seconds=time.time() - start_time,
            )

    def _parse_local_api(
        self,
        path: Path,
        output_format: str,
        enable_ocr: bool,
        enable_formula: bool,
        enable_table: bool,
        start_time: float,
    ) -> MinerUParseResult:
        """本地API解析 (/parse) - 旧版同步API"""
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

    def _parse_cloud_api_official(
        self,
        path: Path,
        output_format: str,
        enable_ocr: bool,
        enable_formula: bool,
        enable_table: bool,
        start_time: float,
    ) -> MinerUParseResult:
        """
        云端官方API解析 - 新版异步流程

        已确认步骤：
        1. 申请上传链接 POST /api/v4/file-urls/batch
        2. PUT 上传文件

        待确认步骤：
        3. 基于 batch_id 查询任务/结果的官方接口
        4. 下载 ZIP 并提取 full.md
        """
        logger.info("Using official cloud API (async flow)")

        # ==========================================
        # 步骤1: 申请上传链接
        # ==========================================
        logger.info("Step 1: Apply for upload URL")
        apply_url = f"{self.api_base}/api/v4/file-urls/batch"

        apply_data = {
            "files": [
                {
                    "name": path.name,
                    "is_ocr": enable_ocr,
                }
            ],
            "model_version": self.model_version,
            "enable_formula": enable_formula,
            "enable_table": enable_table,
            "language": "ch",
        }

        @retry_on_failure(max_retries=3, base_delay=2.0)
        def _apply_upload():
            resp = self.session.post(
                apply_url,
                json=apply_data,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()

        apply_result = _apply_upload()

        if apply_result.get("code") != 0:
            return MinerUParseResult(
                success=False,
                error=f"Failed to apply upload URL: {apply_result.get('msg', 'Unknown error')}",
                parse_time_seconds=time.time() - start_time,
            )

        batch_id = apply_result["data"]["batch_id"]
        upload_url = apply_result["data"]["file_urls"][0]
        logger.info(f"Got upload URL, batch_id: {batch_id}")

        # ==========================================
        # 步骤2: PUT上传文件
        # ==========================================
        logger.info("Step 2: Upload file")

        @retry_on_failure(max_retries=3, base_delay=3.0)
        def _upload_file():
            with open(path, "rb") as f:
                resp = requests.put(
                    upload_url,
                    data=f,
                    timeout=self.timeout,
                )
            resp.raise_for_status()
            return resp

        _upload_file()
        logger.info("File uploaded successfully")

        # ==========================================
        # 步骤3: 轮询批量结果
        # ==========================================
        logger.info("Step 3: Polling batch result")
        batch_result = self._poll_batch_result(batch_id)
        if not batch_result["success"]:
            # 批量查询失败，给出友好提示
            parse_time = time.time() - start_time
            return MinerUParseResult(
                success=False,
                error=(
                    "MinerU 官方云端API批量查询接口正在完善中。\n"
                    "建议使用以下方式之一：\n"
                    "1. 使用本地 MinerU API 服务 (设置 MINERU_API_BASE=http://localhost:8008)\n"
                    "2. 或设置 MINERU_ENABLED=false 使用 PyPDF 解析\n"
                    "3. 或使用模拟模式运行: python examples/tender_compliance_demo.py"
                ),
                raw_json=batch_result.get("raw_json"),
                parse_time_seconds=parse_time,
            )

        # ==========================================
        # 步骤4: 下载 ZIP 并提取 Markdown
        # ==========================================
        logger.info("Step 4: Download and extract result ZIP")
        zip_result = self._download_and_extract_markdown(batch_result["full_zip_url"])
        if not zip_result["success"]:
            return MinerUParseResult(
                success=False,
                error=zip_result["error"],
                raw_json=batch_result.get("raw_json"),
                parse_time_seconds=time.time() - start_time,
            )

        parse_time = time.time() - start_time
        return MinerUParseResult(
            success=True,
            markdown=zip_result.get("markdown"),
            raw_json=batch_result.get("raw_json"),
            parse_time_seconds=parse_time,
            page_count=batch_result.get("page_count", 0),
            table_count=0,
        )

    def _poll_batch_result(self, batch_id: str) -> Dict[str, Any]:
        """轮询批量解析结果"""
        poll_url = f"{self.api_base}/api/v4/extract-results/batch/{batch_id}"
        logger.info(f"Polling batch result: {poll_url}")

        @retry_on_failure(max_retries=2, base_delay=1.0)
        def _poll_once():
            """单次轮询请求（带重试）"""
            resp = self.session.get(poll_url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()

        for i in range(self.max_polls):
            try:
                result = _poll_once()

                # 调试日志：打印完整响应
                if i == 0:
                    logger.debug(f"API Response: {result}")

                if result.get("code") != 0:
                    return {
                        "success": False,
                        "error": f"Batch result query failed: {result.get('msg', 'Unknown error')}",
                        "raw_json": result,
                    }

                data = result.get("data", {})
                state = data.get("state")

                if state == "done":
                    logger.info("Batch parsing completed!")
                    return {
                        "success": True,
                        "full_zip_url": data.get("full_zip_url"),
                        "page_count": 0,
                        "raw_json": result,
                    }
                elif state == "failed":
                    return {
                        "success": False,
                        "error": f"Batch parsing failed: {data.get('err_msg', 'Unknown error')}",
                        "raw_json": result,
                    }
                elif state in ("pending", "running", "converting"):
                    logger.info(f"State: {state}, waiting {self.poll_interval}s...")
                    time.sleep(self.poll_interval)
                elif state is None:
                    # 状态可能在其他字段中，或者需要先等待自动扫描
                    logger.info(f"State is None, waiting for auto-scan... ({i+1}/{self.max_polls})")
                    time.sleep(self.poll_interval)
                else:
                    logger.info(f"Unknown state: {state}, waiting {self.poll_interval}s...")
                    time.sleep(self.poll_interval)

            except Exception as e:
                logger.warning(f"Poll attempt {i+1} failed: {e}")
                time.sleep(self.poll_interval)

        return {
            "success": False,
            "error": f"Timeout polling batch result after {self.max_polls} attempts",
        }

    def _download_and_extract_markdown(self, zip_url: str) -> Dict[str, Any]:
        """下载ZIP并提取full.md"""
        logger.info("Downloading result ZIP...")

        @retry_on_failure(max_retries=3, base_delay=2.0)
        def _download_zip():
            resp = requests.get(zip_url, timeout=self.timeout)
            resp.raise_for_status()
            return resp

        zip_resp = _download_zip()

        logger.info("Extracting full.md from ZIP...")
        with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
            for name in zf.namelist():
                if name.endswith("full.md"):
                    return {
                        "success": True,
                        "markdown": zf.read(name).decode("utf-8"),
                    }

        return {
            "success": False,
            "error": "full.md not found in ZIP",
        }

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

    # 从环境变量读取额外配置（如果有）
    model_version = os.getenv("MINERU_MODEL_VERSION", "vlm")
    poll_interval = int(os.getenv("MINERU_POLL_INTERVAL", "5"))
    max_polls = int(os.getenv("MINERU_MAX_POLLS", "60"))

    return MinerUClient(
        api_base=config.mineru.api_base,
        api_key=config.mineru.api_key,
        timeout=config.mineru.timeout,
        model_version=model_version,
        poll_interval=poll_interval,
        max_polls=max_polls,
    )
