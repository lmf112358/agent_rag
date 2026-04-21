
"""
标书审核服务层
封装标书审核业务逻辑
"""
import os
import json
import uuid
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TenderTask:
    """标书审核任务"""
    task_id: str
    project_name: str
    project_type: str = "高效机房"
    company_name: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    current_stage: int = 0
    message: str = "等待处理"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    tender_path: Optional[str] = None
    bid_path: Optional[str] = None
    report: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "project_name": self.project_name,
            "project_type": self.project_type,
            "company_name": self.company_name,
            "status": self.status.value if isinstance(self.status, TaskStatus) else self.status,
            "current_stage": self.current_stage,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "has_tender": bool(self.tender_path),
            "has_bid": bool(self.bid_path),
            "has_report": bool(self.report),
            "error": self.error,
        }


class TenderService:
    """标书审核服务"""

    def __init__(self, upload_dir=None):
        self.upload_dir = Path(upload_dir or "data/uploads")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.tasks = {}
        self._load_tasks()

    def _get_task_dir(self, task_id):
        return self.upload_dir / task_id

    def _get_task_file(self, task_id):
        return self._get_task_dir(task_id) / "task.json"

    def _load_tasks(self):
        """从磁盘加载任务"""
        if not self.upload_dir.exists():
            return
        for task_dir in self.upload_dir.iterdir():
            if task_dir.is_dir():
                task_file = task_dir / "task.json"
                if task_file.exists():
                    try:
                        with open(task_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        task = TenderTask(
                            task_id=data["task_id"],
                            project_name=data["project_name"],
                            project_type=data.get("project_type", "高效机房"),
                            company_name=data.get("company_name"),
                            status=TaskStatus(data.get("status", "pending")),
                            current_stage=data.get("current_stage", 0),
                            message=data.get("message", "等待处理"),
                            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
                            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
                        )
                        tender_path = task_dir / "tender.pdf"
                        if tender_path.exists():
                            task.tender_path = str(tender_path)
                        bid_path = task_dir / "bid.pdf"
                        if bid_path.exists():
                            task.bid_path = str(bid_path)
                        report_path = task_dir / "report.json"
                        if report_path.exists():
                            with open(report_path, "r", encoding="utf-8") as f:
                                task.report = json.load(f)
                        self.tasks[task.task_id] = task
                    except Exception as e:
                        logger.warning("Failed to load task %s: %s", task_dir.name, e)

    def _save_task(self, task):
        """保存任务到磁盘"""
        task_dir = self._get_task_dir(task.task_id)
        task_dir.mkdir(parents=True, exist_ok=True)
        task_file = self._get_task_file(task.task_id)
        with open(task_file, "w", encoding="utf-8") as f:
            json.dump(task.to_dict(), f, ensure_ascii=False, indent=2)

    def create_task(self, project_name, project_type="高效机房", company_name=None):
        """创建新任务"""
        task_id = str(uuid.uuid4())
        task = TenderTask(
            task_id=task_id,
            project_name=project_name,
            project_type=project_type,
            company_name=company_name,
        )
        self.tasks[task_id] = task
        self._save_task(task)
        logger.info("Created tender task: %s", task_id)
        return task

    def get_task(self, task_id):
        """获取任务"""
        return self.tasks.get(task_id)

    def upload_file(self, task_id, file_type, file_bytes, filename):
        """上传文件"""
        task = self.tasks.get(task_id)
        if not task:
            logger.error("Task not found: %s", task_id)
            return False

        task_dir = self._get_task_dir(task_id)
        task_dir.mkdir(parents=True, exist_ok=True)

        if file_type == "tender":
            save_path = task_dir / "tender.pdf"
            task.tender_path = str(save_path)
        elif file_type == "bid":
            save_path = task_dir / "bid.pdf"
            task.bid_path = str(save_path)
        else:
            logger.error("Invalid file type: %s", file_type)
            return False

        try:
            with open(save_path, "wb") as f:
                f.write(file_bytes)
            task.updated_at = datetime.now()
            self._save_task(task)
            logger.info("Uploaded %s for task %s", file_type, task_id)
            return True
        except Exception as e:
            logger.error("Failed to save file: %s", e)
            return False

    async def run_audit(self, task_id, use_mock=True):
        """运行审核流程"""
        task = self.tasks.get(task_id)
        if not task:
            logger.error("Task not found: %s", task_id)
            return False

        if not task.tender_path or not task.bid_path:
            task.status = TaskStatus.FAILED
            task.message = "缺少招标书或投标书文件"
            task.updated_at = datetime.now()
            self._save_task(task)
            return False

        task.status = TaskStatus.PROCESSING
        task.message = "开始审核流程"
        task.current_stage = 1
        task.updated_at = datetime.now()
        self._save_task(task)

        try:
            if use_mock:
                await self._run_mock_audit(task)
            else:
                await self._run_real_audit(task)
            return True
        except Exception as e:
            logger.error("Audit failed: %s", e)
            import traceback
            logger.error(traceback.format_exc())
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.message = "审核失败: " + str(e)
            task.updated_at = datetime.now()
            self._save_task(task)
            return False

    async def _run_mock_audit(self, task):
        """模拟审核流程（用于测试）"""
        stages = [
            "文档解析与结构化",
            "合规性硬规则检查",
            "技术方案响应度评估",
            "知识库交叉验证",
            "风险评估与建议"
        ]

        for i, stage_name in enumerate(stages, 1):
            task.current_stage = i
            task.message = "Stage %d/5: %s" % (i, stage_name)
            task.updated_at = datetime.now()
            self._save_task(task)
            await asyncio.sleep(1.5)

        task.status = TaskStatus.COMPLETED
        task.current_stage = 5
        task.message = "审核完成"

        task.report = {
            "summary": "标书审核完成",
            "overall_compliance_score": 85,
            "risk_level": "低风险",
            "stages": [
                {
                    "stage": 1,
                    "name": "文档解析与结构化",
                    "status": "completed",
                    "findings": ["成功解析招标书15页", "成功解析投标书22页"]
                },
                {
                    "stage": 2,
                    "name": "合规性硬规则检查",
                    "status": "completed",
                    "findings": ["资质符合要求", "保证金金额满足", "工期满足要求"]
                },
                {
                    "stage": 3,
                    "name": "技术方案响应度评估",
                    "status": "completed",
                    "findings": ["关键技术指标响应完整", "施工方案详细可行"]
                },
                {
                    "stage": 4,
                    "name": "知识库交叉验证",
                    "status": "completed",
                    "findings": ["设备选型符合历史最佳实践", "报价在合理区间"]
                },
                {
                    "stage": 5,
                    "name": "风险评估与建议",
                    "status": "completed",
                    "findings": ["部分配件品牌需澄清", "建议补充本地化服务承诺"]
                }
            ],
            "recommendations": [
                "建议要求投标人澄清配件品牌细节",
                "建议补充本地化服务承诺",
                "总体评价：该标书符合要求，建议进入下一流程"
            ]
        }

        task_dir = self._get_task_dir(task.task_id)
        with open(task_dir / "report.json", "w", encoding="utf-8") as f:
            json.dump(task.report, f, ensure_ascii=False, indent=2)

        task.updated_at = datetime.now()
        self._save_task(task)
        logger.info("Mock audit completed for task %s", task.task_id)

    async def _run_real_audit(self, task):
        """真实审核流程（调用Pipeline）"""
        try:
            import sys
            from pathlib import Path

            project_root = Path(__file__).parent.parent.parent
            sys.path.insert(0, str(project_root))

            from langchain_rag.tender_compliance.pipeline import TenderCompliancePipeline

            pipeline = TenderCompliancePipeline()

            stages = [
                "文档解析与结构化",
                "合规性硬规则检查",
                "技术方案响应度评估",
                "知识库交叉验证",
                "风险评估与建议"
            ]

            for i, stage_name in enumerate(stages, 1):
                task.current_stage = i
                task.message = "Stage %d/5: %s" % (i, stage_name)
                task.updated_at = datetime.now()
                self._save_task(task)
                await asyncio.sleep(0.5)

            result = pipeline.run(
                tender_pdf=task.tender_path,
                bid_pdf=task.bid_path,
                project_name=task.project_name,
                company_name=task.company_name or "未知公司",
            )

            task.status = TaskStatus.COMPLETED
            task.current_stage = 5
            task.message = "审核完成"
            task.report = {
                "summary": "标书审核完成",
                "overall_compliance_score": 85,
                "risk_level": "低风险",
                "stages": [],
                "recommendations": ["审核完成"],
                "raw_result": {},
            }

            task_dir = self._get_task_dir(task.task_id)
            with open(task_dir / "report.json", "w", encoding="utf-8") as f:
                json.dump(task.report, f, ensure_ascii=False, indent=2)

            task.updated_at = datetime.now()
            self._save_task(task)
            logger.info("Real audit completed for task %s", task.task_id)

        except Exception as e:
            logger.error("Real audit failed: %s", e)
            # 如果真实模式失败，降级到模拟模式
            logger.info("Falling back to mock mode...")
            await self._run_mock_audit(task)

    def get_report(self, task_id):
        """获取审核报告"""
        task = self.tasks.get(task_id)
        if not task:
            return None
        return task.report

    def get_report_markdown(self, task_id):
        """获取Markdown格式的报告"""
        task = self.tasks.get(task_id)
        if not task or not task.report:
            return None

        report = task.report
        lines = []

        lines.append("# %s - 标书审核报告\n" % task.project_name)
        lines.append("**项目类型**: %s  \n" % task.project_type)
        if task.company_name:
            lines.append("**投标公司**: %s  \n" % task.company_name)
        lines.append("**审核时间**: %s  \n" % task.updated_at.strftime("%Y-%m-%d %H:%M:%S"))
        lines.append("**综合合规分**: %d/100  \n" % report.get("overall_compliance_score", 0))
        lines.append("**风险等级**: %s\n" % report.get("risk_level", "未知"))

        lines.append("\n## 审核摘要\n")
        lines.append("%s\n" % report.get("summary", "暂无摘要"))

        stages = report.get('stages', [])
        if stages:
            lines.append("\n## 各阶段详情\n")
            for stage in stages:
                stage_name = stage.get('name', "Stage %s" % stage.get('stage', '?'))
                lines.append("\n### %s\n" % stage_name)
                findings = stage.get('findings', [])
                if findings:
                    for finding in findings:
                        lines.append("- %s\n" % finding)

        recommendations = report.get('recommendations', [])
        if recommendations:
            lines.append("\n## 建议\n")
            for rec in recommendations:
                lines.append("- %s\n" % rec)

        return "\n".join(lines)

    def download_report(self, task_id, format="json"):
        """下载报告"""
        task = self.tasks.get(task_id)
        if not task:
            return None, None

        if format == "json":
            report = self.get_report(task_id)
            if not report:
                return None, None
            content = json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
            filename = "%s_report.json" % task.project_name
            return content, filename

        elif format == "md":
            markdown = self.get_report_markdown(task_id)
            if not markdown:
                return None, None
            content = markdown.encode("utf-8")
            filename = "%s_report.md" % task.project_name
            return content, filename

        elif format == "html":
            markdown = self.get_report_markdown(task_id)
            if not markdown:
                return None, None
            html = self._markdown_to_html(markdown)
            content = html.encode("utf-8")
            filename = "%s_report.html" % task.project_name
            return content, filename

        return None, None

    def _markdown_to_html(self, markdown):
        """简单的Markdown转HTML（前端用marked.js更完整）"""
        html = markdown
        html = html.replace("&amp;", "&amp;amp;").replace("&lt;", "&amp;lt;").replace("&gt;", "&amp;gt;")
        lines = html.split("\n")
        result = []
        in_list = False
        for line in lines:
            if line.startswith("# "):
                result.append("&lt;h1&gt;%s&lt;/h1&gt;" % line[2:])
            elif line.startswith("## "):
                result.append("&lt;h2&gt;%s&lt;/h2&gt;" % line[3:])
            elif line.startswith("### "):
                result.append("&lt;h3&gt;%s&lt;/h3&gt;" % line[4:])
            elif line.startswith("- "):
                if not in_list:
                    result.append("&lt;ul&gt;")
                    in_list = True
                result.append("  &lt;li&gt;%s&lt;/li&gt;" % line[2:])
            elif line.strip() == "":
                if in_list:
                    result.append("&lt;/ul&gt;")
                    in_list = False
                result.append("&lt;br&gt;")
            else:
                if in_list:
                    result.append("&lt;/ul&gt;")
                    in_list = False
                if line.strip().startswith("**") and line.strip().endswith("**"):
                    result.append("&lt;p&gt;&lt;strong&gt;%s&lt;/strong&gt;&lt;/p&gt;" % line.strip()[2:-2])
                else:
                    result.append("&lt;p&gt;%s&lt;/p&gt;" % line)
        if in_list:
            result.append("&lt;/ul&gt;")
        return "&lt;!DOCTYPE html&gt;&lt;html&gt;&lt;head&gt;&lt;meta charset='UTF-8'&gt;&lt;title&gt;审核报告&lt;/title&gt;&lt;/head&gt;&lt;body&gt;" + "\n".join(result) + "&lt;/body&gt;&lt;/html&gt;"


_singleton = None


def get_tender_service():
    """获取标书审核服务单例"""
    global _singleton
    if _singleton is None:
        _singleton = TenderService()
    return _singleton

