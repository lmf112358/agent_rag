"""
标书审核Pipeline主类

集成5阶段Pipeline：
1. 文档解析层 (Stage1Parser)
2. 条款对齐层 (Stage2Aligner)
3. 核对引擎层 (Stage3Compliance)
4. 评分汇总层 (Stage4Scoring)
5. 人工复核层 (Stage5Review)
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, Union
from datetime import datetime

from .models import (
    TenderDocument,
    BidDocument,
    TenderChecklist,
    BidResponse,
    ComplianceResult,
    ScoringCard,
    ReviewReport,
    DocumentParseResult,
)
from .config import REPORT_TEMPLATE, AUTO_DECISION_RULES

logger = logging.getLogger(__name__)


class TenderCompliancePipeline:
    """
    标书审核合规性Pipeline主类

    使用示例：
        pipeline = TenderCompliancePipeline()
        result = pipeline.run(
            tender_pdf="/path/to/tender.pdf",
            bid_pdf="/path/to/bid.pdf",
            project_name="珠海某PCB厂高效机房项目"
        )
    """

    def __init__(
        self,
        mineru_api_base: Optional[str] = None,
        mineru_api_key: Optional[str] = None,
        qdrant_host: Optional[str] = None,
        llm_model: Optional[str] = None,
        enable_kb_verify: bool = True,
    ):
        """
        初始化Pipeline

        Args:
            mineru_api_base: MinerU API服务地址
            mineru_api_key: MinerU API密钥
            qdrant_host: Qdrant向量库地址
            llm_model: LLM模型名称
            enable_kb_verify: 是否启用知识库校验
        """
        import os
        from dotenv import load_dotenv

        # 加载.env文件
        load_dotenv("langchain_rag/.env")

        # 从环境变量读取默认值
        self.mineru_api_base = mineru_api_base or os.getenv("MINERU_API_BASE", "http://localhost:8008")
        self.mineru_api_key = mineru_api_key or os.getenv("MINERU_API_KEY", "")
        self.qdrant_host = qdrant_host or os.getenv("QDRANT_HOST", "localhost")
        self.llm_model = llm_model or os.getenv("LLM_MODEL_NAME", "qwen-max")
        self.enable_kb_verify = enable_kb_verify

        # 延迟初始化各Stage处理器
        self._stage1_parser = None
        self._stage2_aligner = None
        self._stage3_compliance = None
        self._stage4_scoring = None
        self._stage5_review = None

        logger.info(f"TenderCompliancePipeline initialized with llm_model={llm_model}")

    @property
    def stage1_parser(self):
        """延迟初始化Stage1"""
        if self._stage1_parser is None:
            from .stage1_parser import Stage1Parser
            self._stage1_parser = Stage1Parser(
                mineru_api_base=self.mineru_api_base,
                mineru_api_key=self.mineru_api_key,
            )
        return self._stage1_parser

    @property
    def stage2_aligner(self):
        """延迟初始化Stage2"""
        if self._stage2_aligner is None:
            from .stage2_aligner import Stage2Aligner
            self._stage2_aligner = Stage2Aligner(
                llm_model=self.llm_model
            )
        return self._stage2_aligner

    @property
    def stage3_compliance(self):
        """延迟初始化Stage3"""
        if self._stage3_compliance is None:
            from .stage3_compliance import Stage3Compliance
            self._stage3_compliance = Stage3Compliance(
                llm_model=self.llm_model,
                qdrant_host=self.qdrant_host,
                enable_kb_verify=self.enable_kb_verify
            )
        return self._stage3_compliance

    @property
    def stage4_scoring(self):
        """延迟初始化Stage4"""
        if self._stage4_scoring is None:
            from .stage4_scoring import Stage4Scoring
            self._stage4_scoring = Stage4Scoring()
        return self._stage4_scoring

    @property
    def stage5_review(self):
        """延迟初始化Stage5"""
        if self._stage5_review is None:
            from .stage5_review import Stage5Review
            self._stage5_review = Stage5Review()
        return self._stage5_review

    def run(
        self,
        tender_pdf: str,
        bid_pdf: str,
        project_name: Optional[str] = None,
        project_type: str = "高效机房",
        company_name: Optional[str] = None,
        save_intermediate: bool = True,
    ) -> ReviewReport:
        """
        执行完整的标书审核Pipeline

        Args:
            tender_pdf: 招标书PDF文件路径
            bid_pdf: 投标书PDF文件路径
            project_name: 项目名称
            project_type: 项目类型
            company_name: 投标公司名称
            save_intermediate: 是否保存中间结果

        Returns:
            ReviewReport: 完整审核报告
        """
        import uuid

        tender_id = f"TENDER_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
        bid_id = f"BID_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"

        logger.info(f"=" * 60)
        logger.info(f"启动标书审核Pipeline")
        logger.info(f"招标书: {tender_pdf}")
        logger.info(f"投标书: {bid_pdf}")
        logger.info(f"=" * 60)

        # ==================== Stage 1: 文档解析层 ====================
        logger.info("[Stage 1] 文档解析层...")
        tender_doc, bid_doc = self.stage1_parser.parse(
            tender_pdf=tender_pdf,
            bid_pdf=bid_pdf,
            tender_id=tender_id,
            bid_id=bid_id,
            project_name=project_name or "未命名项目",
            project_type=project_type,
            company_name=company_name or "未命名公司"
        )
        logger.info(f"  招标书解析完成: {tender_doc.parse_result.page_count}页")
        logger.info(f"  投标书解析完成: {bid_doc.parse_result.page_count}页")

        # ==================== Stage 2: 条款对齐层 ====================
        logger.info("[Stage 2] 条款对齐层...")
        checklist, bid_response = self.stage2_aligner.align(
            tender_doc=tender_doc,
            bid_doc=bid_doc
        )
        logger.info(f"  提取招标条款: {len(checklist.items)}条")
        logger.info(f"  提取投标响应: {len(bid_response.equipment_tables)}个设备表")

        # ==================== Stage 3: 核对引擎层 ====================
        logger.info("[Stage 3] 核对引擎层...")
        compliance_result = self.stage3_compliance.check(
            checklist=checklist,
            bid_response=bid_response
        )
        logger.info(f"  核对完成: {len(compliance_result.checks)}项")

        # ==================== Stage 4: 评分汇总层 ====================
        logger.info("[Stage 4] 评分汇总层...")
        scoring_card = self.stage4_scoring.score(
            checklist=checklist,
            compliance_result=compliance_result
        )
        logger.info(f"  总得分: {scoring_card.total_score}/{scoring_card.max_total_score}")
        logger.info(f"  废标风险: {'有' if scoring_card.disqualification_risk else '无'}")

        # ==================== Stage 5: 人工复核层 ====================
        logger.info("[Stage 5] 人工复核层...")
        review_report = self.stage5_review.generate_report(
            tender_doc=tender_doc,
            bid_doc=bid_doc,
            checklist=checklist,
            bid_response=bid_response,
            compliance_result=compliance_result,
            scoring_card=scoring_card
        )
        logger.info(f"  报告生成完成: {review_report.report_id}")

        logger.info(f"=" * 60)
        logger.info(f"标书审核Pipeline完成")
        logger.info(f"=" * 60)

        return review_report

    def run_stage_only(
        self,
        stage: int,
        **kwargs
    ) -> Any:
        """
        仅执行指定Stage（用于调试）

        Args:
            stage: Stage编号 (1-5)
            **kwargs: 该Stage所需的输入参数

        Returns:
            该Stage的输出结果
        """
        if stage == 1:
            return self.stage1_parser.parse(**kwargs)
        elif stage == 2:
            return self.stage2_aligner.align(**kwargs)
        elif stage == 3:
            return self.stage3_compliance.check(**kwargs)
        elif stage == 4:
            return self.stage4_scoring.score(**kwargs)
        elif stage == 5:
            return self.stage5_review.generate_report(**kwargs)
        else:
            raise ValueError(f"Invalid stage: {stage}")

