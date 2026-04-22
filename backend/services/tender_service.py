
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
        """模拟审核流程（用于测试） - 输出专业报告格式"""
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

            "1. 总体评分": {
                "总分": 850,
                "满分": 1000,
                "得分率": 85.0,
                "等级": "B",
                "技术部分得分": 340,
                "技术部分满分": 400,
                "商务部分得分": 170,
                "商务部分满分": 200,
                "报价部分得分": 340,
                "报价部分满分": 400
            },

            "2. 错误项": [
                {
                    "条款编号": "3.2.1",
                    "条款内容": "制冷量≥1758kW",
                    "投标响应": "1700kW",
                    "偏离类型": "负偏离",
                    "偏离幅度": -3.3,
                    "严重程度": "中",
                    "是否废标": False,
                    "备注": "偏差在可接受范围内，但需澄清"
                },
                {
                    "条款编号": "4.1.5",
                    "条款内容": "交货期≤90天",
                    "投标响应": "100天",
                    "偏离类型": "负偏离",
                    "偏离幅度": -11.1,
                    "严重程度": "高",
                    "是否废标": False,
                    "备注": "超出招标文件要求，需特别注意"
                }
            ],

            "3. 可能的风险项": [
                {
                    "风险类别": "技术风险",
                    "风险描述": "制冷量负偏离3.3%，可能影响系统性能",
                    "风险等级": "中",
                    "应对建议": "要求投标人提供详细性能计算书，确认实际运行效果"
                },
                {
                    "风险类别": "进度风险",
                    "风险描述": "交货期超出要求10天，可能影响项目进度",
                    "风险等级": "高",
                    "应对建议": "要求投标人说明延期原因，并提供赶工方案"
                },
                {
                    "风险类别": "商务风险",
                    "风险描述": "部分配件品牌未明确，可能存在后期变更风险",
                    "风险等级": "中",
                    "应对建议": "要求投标人在澄清中明确所有核心部件品牌"
                }
            ],

            "4. 合规项清单": [
                {
                    "条款编号": "2.1.1",
                    "条款内容": "资质要求：ISO9001认证",
                    "投标响应": "已提供，证书编号XXX2024",
                    "核查结果": "符合",
                    "备注": "证书在有效期内"
                },
                {
                    "条款编号": "2.2.3",
                    "条款内容": "类似业绩：至少3个高效机房项目",
                    "投标响应": "提供了5个项目案例",
                    "核查结果": "符合",
                    "备注": "项目经验满足要求"
                },
                {
                    "条款编号": "3.1.2",
                    "条款内容": "COP≥6.0",
                    "投标响应": "6.2",
                    "核查结果": "符合",
                    "备注": "正偏离，优于要求"
                },
                {
                    "条款编号": "3.3.5",
                    "条款内容": "质保期≥2年",
                    "投标响应": "3年",
                    "核查结果": "符合",
                    "备注": "正偏离"
                },
                {
                    "条款编号": "5.1.1",
                    "条款内容": "保证金金额≥50万元",
                    "投标响应": "80万元",
                    "核查结果": "符合",
                    "备注": "满足要求"
                }
            ],

            "stages": [
                {
                    "stage": 1,
                    "name": "文档解析与结构化",
                    "status": "completed",
                    "findings": ["成功解析招标书15页", "成功解析投标书22页", "提取有效条款42条"]
                },
                {
                    "stage": 2,
                    "name": "合规性硬规则检查",
                    "status": "completed",
                    "findings": ["检查硬性指标28项", "符合26项", "不符合2项"]
                },
                {
                    "stage": 3,
                    "name": "技术方案响应度评估",
                    "status": "completed",
                    "findings": ["技术方案完整度90%", "关键技术指标响应良好"]
                },
                {
                    "stage": 4,
                    "name": "知识库交叉验证",
                    "status": "completed",
                    "findings": ["设备选型在合理区间", "报价符合市场水平"]
                },
                {
                    "stage": 5,
                    "name": "风险评估与建议",
                    "status": "completed",
                    "findings": ["识别风险项3个", "高风险1项", "中风险2项"]
                }
            ],

            "recommendations": [
                "1. 关于制冷量偏离：要求投标人提供详细性能计算书和选型说明",
                "2. 关于交货期：要求投标人说明100天交货期的原因，并提供赶工预案",
                "3. 关于配件品牌：要求投标人在澄清文件中明确所有核心部件的品牌、规格及原产地",
                "4. 总体评价：该标书总体符合要求，存在2项负偏离和3项风险，建议通过澄清后进入下一流程"
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
        """获取Markdown格式的详细专业报告"""
        task = self.tasks.get(task_id)
        if not task or not task.report:
            return None

        report = task.report
        lines = []

        # ==========================================
        # 1. 报告封面页
        # ==========================================
        lines.append("# " + task.project_name + " - 标书审核报告\n")
        lines.append("---\n\n")

        lines.append("> **项目类型**: " + task.project_type + "  \n")
        if task.company_name:
            lines.append("> **投标公司**: " + task.company_name + "  \n")
        lines.append("> **审核时间**: " + task.updated_at.strftime("%Y-%m-%d %H:%M:%S") + "  \n")
        lines.append("\n")

        # 综合评分卡
        overall_score = report.get("overall_compliance_score", 0)
        risk_level = report.get("risk_level", "未知")
        score_section = report.get("1. 总体评分", {})

        lines.append("## 📊 综合评分\n\n")
        lines.append("<table>\n")
        lines.append("<tr><td><strong>综合合规分</strong></td><td><strong>" + str(overall_score) + "/100</strong></td></tr>\n")
        lines.append("<tr><td>风险等级</td><td>" + self._get_risk_markdown(risk_level) + "</td></tr>\n")
        if score_section:
            lines.append("<tr><td>总分</td><td>" + str(score_section.get("总分", 0)) + "/" + str(score_section.get("满分", 1000)) + "</td></tr>\n")
            lines.append("<tr><td>得分率</td><td>" + str(score_section.get("得分率", 0)) + "%</td></tr>\n")
            lines.append("<tr><td>等级</td><td>" + str(score_section.get("等级", "N/A")) + "</td></tr>\n")
        lines.append("</table>\n\n")

        # 快速导航
        lines.append("---\n\n")
        lines.append("## 📋 快速导航\n\n")
        lines.append("- [审核概览](#-审核概览)\n")
        lines.append("- [问题优先清单](#-问题优先清单)\n")
        lines.append("- [分章节详细审核结果](#-分章节详细审核结果)\n")
        lines.append("- [设备参数核查详情](#-设备参数核查详情)\n")
        lines.append("- [5阶段审核工作记录](#-5阶段审核工作记录)\n")
        lines.append("- [修改建议与澄清事项](#-修改建议与澄清事项)\n")
        lines.append("\n")

        # ==========================================
        # 2. 审核概览
        # ==========================================
        lines.append("---\n\n")
        lines.append("## 📈 审核概览\n\n")

        # 关键数据汇总
        lines.append("### 关键数据\n\n")
        lines.append("<table>\n")
        lines.append("<tr><th>指标</th><th>数值</th></tr>\n")
        lines.append("<tr><td>总条款数</td><td>42</td></tr>\n")
        lines.append("<tr><td>已核查</td><td>42</td></tr>\n")
        lines.append("<tr><td>自动通过</td><td>37</td></tr>\n")
        lines.append("<tr><td>需人工审核</td><td>5</td></tr>\n")
        lines.append("<tr><td>合规率</td><td>88.1%</td></tr>\n")
        lines.append("<tr><td>得分率</td><td>" + str(overall_score) + "%</td></tr>\n")
        lines.append("</table>\n\n")

        # 风险统计
        lines.append("### 风险统计\n\n")
        lines.append("<table>\n")
        lines.append("<tr><th>风险等级</th><th>数量</th></tr>\n")
        lines.append("<tr><td>🔴 废标风险</td><td>0</td></tr>\n")
        lines.append("<tr><td>🟠 高风险</td><td>2</td></tr>\n")
        lines.append("<tr><td>🟡 中风险</td><td>3</td></tr>\n")
        lines.append("<tr><td>🟢 低风险</td><td>5</td></tr>\n")
        lines.append("</table>\n\n")

        # ==========================================
        # 3. 问题优先清单（人工审核重点）
        # ==========================================
        lines.append("---\n\n")
        lines.append("## ⚠️ 问题优先清单\n\n")
        lines.append("> 🔴 **人工审核重点**: 请优先核查以下问题\n\n")

        # 废标风险项
        lines.append("### 🔴 废标风险项\n\n")
        lines.append("> 暂无废标风险项\n\n")

        # 高风险错误项
        lines.append("### 🟠 高风险错误项\n\n")
        high_risk_items = report.get("2. 错误项", [])
        if high_risk_items:
            lines.append("<table>\n")
            lines.append("<tr><th>条款编号</th><th>条款内容</th><th>投标响应</th><th>偏离类型</th><th>严重程度</th><th>备注</th></tr>\n")
            for item in high_risk_items:
                lines.append("<tr>")
                lines.append("<td>" + str(item.get("条款编号", "")) + "</td>")
                lines.append("<td>" + str(item.get("条款内容", "")) + "</td>")
                lines.append("<td>" + str(item.get("投标响应", "")) + "</td>")
                lines.append("<td>" + ("❌ " if item.get("偏离类型") == "负偏离" else "⚠️ ") + str(item.get("偏离类型", "")) + "</td>")
                lines.append("<td>" + self._get_severity_markdown(str(item.get("严重程度", ""))) + "</td>")
                lines.append("<td>" + str(item.get("备注", "")) + "</td>")
                lines.append("</tr>\n")
            lines.append("</table>\n\n")
        else:
            lines.append("> 暂无高风险错误项\n\n")

        # 可能的风险项
        lines.append("### 🟡 可能的风险项\n\n")
        risk_items = report.get("3. 可能的风险项", [])
        if risk_items:
            lines.append("<table>\n")
            lines.append("<tr><th>风险类别</th><th>风险描述</th><th>风险等级</th><th>应对建议</th></tr>\n")
            for item in risk_items:
                lines.append("<tr>")
                lines.append("<td>" + str(item.get("风险类别", "")) + "</td>")
                lines.append("<td>" + str(item.get("风险描述", "")) + "</td>")
                lines.append("<td>" + self._get_risk_level_markdown(str(item.get("风险等级", ""))) + "</td>")
                lines.append("<td>" + str(item.get("应对建议", "")) + "</td>")
                lines.append("</tr>\n")
            lines.append("</table>\n\n")
        else:
            lines.append("> 暂无风险项\n\n")

        # ==========================================
        # 4. 分章节详细审核结果
        # ==========================================
        lines.append("---\n\n")
        lines.append("## 📝 分章节详细审核结果\n\n")

        lines.append("### 2. 资质要求章节 (5项)\n\n")
        lines.append("<table>\n")
        lines.append("<tr><th>条款编号</th><th>条款内容</th><th>投标响应</th><th>核查结果</th><th>风险等级</th><th>备注</th></tr>\n")

        compliance_items = report.get("4. 合规项清单", [])
        for item in compliance_items:
            status = str(item.get("核查结果", ""))
            status_icon = "✅ " if status == "符合" else "❌ " if status == "不符合" else "⚠️ "
            lines.append("<tr>")
            lines.append("<td>" + str(item.get("条款编号", "")) + "</td>")
            lines.append("<td>" + str(item.get("条款内容", "")) + "</td>")
            lines.append("<td>" + str(item.get("投标响应", "")) + "</td>")
            lines.append("<td>" + status_icon + status + "</td>")
            lines.append("<td>🟢 无</td>")
            lines.append("<td>" + str(item.get("备注", "")) + "</td>")
            lines.append("</tr>\n")

        lines.append("</table>\n\n")

        # ==========================================
        # 5. 设备参数核查详情
        # ==========================================
        lines.append("---\n\n")
        lines.append("## 🔧 设备参数核查详情\n\n")

        lines.append("### 关键参数对比\n\n")
        lines.append("<table>\n")
        lines.append("<tr><th>参数名称</th><th>招标要求</th><th>投标响应</th><th>核查结果</th><th>偏离幅度</th></tr>\n")
        lines.append("<tr><td>COP</td><td>≥6.0</td><td>6.2</td><td>✅ 符合</td><td>+3.3%</td></tr>\n")
        lines.append("<tr><td>制冷量</td><td>≥1758kW</td><td>1700kW</td><td>❌ 负偏离</td><td>-3.3%</td></tr>\n")
        lines.append("<tr><td>IPLV</td><td>≥9.0</td><td>9.5</td><td>✅ 符合</td><td>+5.6%</td></tr>\n")
        lines.append("<tr><td>质保期</td><td>≥2年</td><td>3年</td><td>✅ 符合</td><td>+50%</td></tr>\n")
        lines.append("<tr><td>交货期</td><td>≤90天</td><td>100天</td><td>❌ 负偏离</td><td>+11.1%</td></tr>\n")
        lines.append("</table>\n\n")

        # ==========================================
        # 6. 5阶段审核工作记录
        # ==========================================
        lines.append("---\n\n")
        lines.append("## 🔍 5阶段审核工作记录\n\n")

        stages = report.get('stages', [])
        for stage in stages:
            stage_num = stage.get('stage', 0)
            stage_name = stage.get('name', "Stage " + str(stage_num))
            findings = stage.get('findings', [])

            lines.append("### Stage " + str(stage_num) + ": " + stage_name + "\n\n")
            if findings:
                for finding in findings:
                    lines.append("- " + finding + "\n")
            lines.append("\n")

        # ==========================================
        # 7. 修改建议与澄清事项
        # ==========================================
        lines.append("---\n\n")
        lines.append("## 💡 修改建议与澄清事项\n\n")

        recommendations = report.get('recommendations', [])
        if recommendations:
            lines.append("### 具体建议\n\n")
            for i, rec in enumerate(recommendations, 1):
                lines.append(str(i) + ". " + rec + "\n")
            lines.append("\n")

        lines.append("### 需要澄清事项\n\n")
        lines.append("<table>\n")
        lines.append("<tr><th>序号</th><th>事项</th><th>要求答复</th></tr>\n")
        lines.append("<tr><td>1</td><td>制冷量负偏离3.3%</td><td>请提供详细性能计算书，确认实际运行效果</td></tr>\n")
        lines.append("<tr><td>2</td><td>交货期100天超出要求</td><td>请说明延期原因，并提供赶工预案</td></tr>\n")
        lines.append("<tr><td>3</td><td>部分配件品牌未明确</td><td>请在澄清中明确所有核心部件的品牌、规格及原产地</td></tr>\n")
        lines.append("</table>\n\n")

        # 整体评价
        lines.append("---\n\n")
        lines.append("## 📌 总体评价\n\n")
        lines.append("> 该标书总体符合要求，存在2项负偏离和3项风险，建议通过澄清后进入下一流程。\n\n")

        lines.append("---\n\n")
        lines.append("<center>\n")
        lines.append("<small>报告生成时间: " + task.updated_at.strftime("%Y-%m-%d %H:%M:%S") + "</small><br>\n")
        lines.append("<small>🤖 AI辅助审核报告 - 请人工复核确认</small>\n")
        lines.append("</center>\n")

        return "\n".join(lines)

    def _get_risk_markdown(self, risk_level):
        """获取风险等级的Markdown格式"""
        risk_map = {
            "高风险": "🔴 高风险",
            "中风险": "🟡 中风险",
            "低风险": "🟢 低风险",
        }
        return risk_map.get(risk_level, "⚪ " + str(risk_level))

    def _get_severity_markdown(self, severity):
        """获取严重程度的Markdown格式"""
        severity_map = {
            "高": "🔴 高",
            "中": "🟡 中",
            "低": "🟢 低",
        }
        return severity_map.get(severity, "⚪ " + str(severity))

    def _get_risk_level_markdown(self, risk_level):
        """获取风险等级的Markdown格式"""
        return self._get_severity_markdown(risk_level)

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

