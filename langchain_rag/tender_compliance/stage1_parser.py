"""
Stage 1: 文档解析层

负责：
1. 调用MinerU进行PDF转Markdown
2. 调用QualityChecker进行文档质量检测
3. 输出解析后的文档对象
"""

import logging
from pathlib import Path
from typing import Optional, Tuple

from .models import (
    TenderDocument,
    BidDocument,
    DocumentParseResult,
)
from ..document.mineru_client import MinerUClient
from ..document.quality_checker import QualityChecker

logger = logging.getLogger(__name__)


class Stage1Parser:
    """
    Stage 1: 文档解析层

    复用现有MinerU和QualityChecker实现
    """

    def __init__(
        self,
        mineru_api_base: str = "http://localhost:8008",
        mineru_api_key: str = "",
        timeout: int = 300,
    ):
        """
        初始化Stage1解析器

        Args:
            mineru_api_base: MinerU API服务地址
            mineru_api_key: MinerU API密钥
            timeout: 解析超时时间（秒）
        """
        self.mineru_client = MinerUClient(
            api_base=mineru_api_base,
            api_key=mineru_api_key,
            timeout=timeout
        )
        self.quality_checker = QualityChecker()

    def parse(
        self,
        tender_pdf: str,
        bid_pdf: str,
        tender_id: str,
        bid_id: str,
        project_name: str,
        project_type: str = "高效机房",
        company_name: str = "未命名公司",
    ) -> Tuple[TenderDocument, BidDocument]:
        """
        解析招标书和投标书PDF

        Args:
            tender_pdf: 招标书PDF路径
            bid_pdf: 投标书PDF路径
            tender_id: 招标书ID
            bid_id: 投标书ID
            project_name: 项目名称
            project_type: 项目类型
            company_name: 投标公司名称

        Returns:
            Tuple[TenderDocument, BidDocument]: 解析后的招标书和投标书对象
        """
        import time
        start_time = time.time()

        logger.info(f"[Stage 1] 开始解析文档")
        logger.info(f"  招标书: {tender_pdf}")
        logger.info(f"  投标书: {bid_pdf}")

        # 解析招标书
        logger.info(f"  解析招标书...")
        tender_start = time.time()
        tender_parse_result = self._parse_single_pdf(tender_pdf)
        tender_elapsed = time.time() - tender_start

        if tender_parse_result.success:
            logger.info(f"    招标书解析成功: {tender_parse_result.page_count}页, 耗时{tender_elapsed:.2f}秒")
            if tender_parse_result.quality_report:
                logger.debug(f"    质量报告: {tender_parse_result.quality_report}")
        else:
            logger.warning(f"    招标书解析失败: {tender_parse_result.error}")

        tender_doc = TenderDocument(
            tender_id=tender_id,
            project_name=project_name,
            project_type=project_type,
            pdf_path=tender_pdf,
            parse_result=tender_parse_result,
            markdown=tender_parse_result.markdown if tender_parse_result.success else None,
        )

        # 解析投标书
        logger.info(f"  解析投标书...")
        bid_start = time.time()
        bid_parse_result = self._parse_single_pdf(bid_pdf)
        bid_elapsed = time.time() - bid_start

        if bid_parse_result.success:
            logger.info(f"    投标书解析成功: {bid_parse_result.page_count}页, 耗时{bid_elapsed:.2f}秒")
            if bid_parse_result.quality_report:
                logger.debug(f"    质量报告: {bid_parse_result.quality_report}")
        else:
            logger.warning(f"    投标书解析失败: {bid_parse_result.error}")

        bid_doc = BidDocument(
            bid_id=bid_id,
            tender_id=tender_id,
            company_name=company_name,
            pdf_path=bid_pdf,
            parse_result=bid_parse_result,
            markdown=bid_parse_result.markdown if bid_parse_result.success else None,
        )

        total_elapsed = time.time() - start_time
        logger.info(f"[Stage 1] 文档解析完成, 总耗时{total_elapsed:.2f}秒")

        return tender_doc, bid_doc

    def _parse_single_pdf(self, pdf_path: str) -> DocumentParseResult:
        """
        解析单个PDF文件

        Args:
            pdf_path: PDF文件路径

        Returns:
            DocumentParseResult: 解析结果
        """
        import time
        from pathlib import Path

        start_time = time.time()

        # 检查文件是否存在
        if not Path(pdf_path).exists():
            logger.error(f"文件不存在: {pdf_path}")
            return DocumentParseResult(
                success=False,
                error=f"文件不存在: {pdf_path}",
                parse_time_seconds=time.time() - start_time,
            )

        # 1. 质量检测
        logger.debug(f"  [1/2] 执行质量检测: {Path(pdf_path).name}")
        quality_report = self.quality_checker.check(pdf_path)
        logger.debug(f"    质量评分: {quality_report.quality_score}, 标签: {quality_report.quality_tag}")
        if quality_report.issues:
            logger.debug(f"    质量问题: {quality_report.issues}")

        if quality_report.quality_score == 0.0:
            logger.warning(f"    质量不合格，跳过解析")
            return DocumentParseResult(
                success=False,
                error=f"文档质量不合格: {', '.join(quality_report.issues)}",
                parse_time_seconds=time.time() - start_time,
            )

        # 2. MinerU解析
        logger.debug(f"  [2/2] 调用MinerU解析: {Path(pdf_path).name}")
        mineru_start = time.time()
        try:
            mineru_result = self.mineru_client.parse_pdf(pdf_path)
            mineru_elapsed = time.time() - mineru_start

            if not mineru_result.success:
                logger.warning(f"    MinerU解析失败: {mineru_result.error}")
                return DocumentParseResult(
                    success=False,
                    error=f"MinerU解析失败: {mineru_result.error}",
                    parse_time_seconds=time.time() - start_time,
                )

            logger.debug(f"    MinerU解析完成: {mineru_result.page_count}页, 耗时{mineru_elapsed:.2f}秒")
            if mineru_result.markdown:
                logger.debug(f"    Markdown长度: {len(mineru_result.markdown)}字符")

            return DocumentParseResult(
                success=True,
                markdown=mineru_result.markdown,
                quality_report={
                    "tag": quality_report.quality_tag,
                    "score": quality_report.quality_score,
                    "issues": quality_report.issues,
                    "page_count": quality_report.page_count,
                },
                page_count=mineru_result.page_count,
                parse_time_seconds=time.time() - start_time,
            )

        except Exception as e:
            logger.exception(f"    解析异常: {str(e)}")
            return DocumentParseResult(
                success=False,
                error=f"解析异常: {str(e)}",
                parse_time_seconds=time.time() - start_time,
            )

    def parse_tender_only(
        self,
        tender_pdf: str,
        tender_id: str,
        project_name: str,
        project_type: str = "高效机房",
    ) -> TenderDocument:
        """
        仅解析招标书（用于预览/模板生成）

        Args:
            tender_pdf: 招标书PDF路径
            tender_id: 招标书ID
            project_name: 项目名称
            project_type: 项目类型

        Returns:
            TenderDocument: 招标书文档对象
        """
        logger.info(f"仅解析招标书: {tender_pdf}")
        tender_parse_result = self._parse_single_pdf(tender_pdf)

        return TenderDocument(
            tender_id=tender_id,
            project_name=project_name,
            project_type=project_type,
            pdf_path=tender_pdf,
            parse_result=tender_parse_result,
            markdown=tender_parse_result.markdown if tender_parse_result.success else None,
        )

