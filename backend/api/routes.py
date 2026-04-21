"""
API路由模块
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import io
from backend.services.rag_service import RAGService
from backend.services.memory_service import MemoryService
from backend.services.agent_service import AgentService
from backend.services.tender_service import (
    get_tender_service,
    TaskStatus,
)

router = APIRouter()


class QueryRequest(BaseModel):
    """查询请求"""
    query: str = Field(..., description="用户查询内容")
    session_id: Optional[str] = Field(None, description="会话ID")
    context: Optional[Dict[str, Any]] = Field(None, description="上下文信息")


class AgentRequest(BaseModel):
    """Agent请求"""
    query: str = Field(..., description="用户查询内容")
    session_id: Optional[str] = Field(None, description="会话ID")
    tools: Optional[List[str]] = Field(None, description="指定使用的工具")


class MemoryRequest(BaseModel):
    """记忆操作请求"""
    session_id: str = Field(..., description="会话ID")
    operation: str = Field(..., description="操作类型: get, clear, save")
    data: Optional[Dict[str, Any]] = Field(None, description="保存的数据")


class Response(BaseModel):
    """通用响应"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    session_id: Optional[str] = None


# ==========================================
# 标书审核相关模型
# ==========================================

class TenderCreateRequest(BaseModel):
    """创建标书审核任务请求"""
    project_name: str = Field(..., description="项目名称")
    projectName: Optional[str] = Field(None, description="项目名称(兼容)")
    project_type: str = Field("高效机房", description="项目类型")
    projectType: Optional[str] = Field(None, description="项目类型(兼容)")
    company_name: Optional[str] = Field(None, description="投标公司名称")
    companyName: Optional[str] = Field(None, description="投标公司名称(兼容)")

    @property
    def effective_project_name(self):
        return self.projectName or self.project_name

    @property
    def effective_project_type(self):
        return self.projectType or self.project_type

    @property
    def effective_company_name(self):
        return self.companyName or self.company_name


class TenderAuditRequest(BaseModel):
    """启动审核请求"""
    task_id: str = Field(..., description="任务ID")
    taskId: Optional[str] = Field(None, description="任务ID(兼容)")
    use_mock: bool = Field(True, description="是否使用模拟模式（快速测试）")
    useMock: Optional[bool] = Field(None, description="是否使用模拟模式(兼容)")

    @property
    def effective_task_id(self):
        return self.taskId or self.task_id

    @property
    def effective_use_mock(self):
        return self.useMock if self.useMock is not None else self.use_mock


@router.post("/rag/query", response_model=Response)
async def rag_query(request: QueryRequest):
    """RAG查询"""
    try:
        service = RAGService()
        result = service.query(
            query=request.query,
            session_id=request.session_id,
            context=request.context
        )
        return Response(
            success=True,
            data=result,
            session_id=result.get("session_id")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent/invoke", response_model=Response)
async def agent_invoke(request: AgentRequest):
    """Agent调用"""
    try:
        service = AgentService()
        result = service.invoke(
            query=request.query,
            session_id=request.session_id,
            tools=request.tools
        )
        return Response(
            success=True,
            data=result,
            session_id=result.get("session_id")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/operation", response_model=Response)
async def memory_operation(request: MemoryRequest):
    """记忆操作"""
    try:
        service = MemoryService()
        if request.operation == "get":
            result = service.get_session(request.session_id)
        elif request.operation == "clear":
            result = service.clear_session(request.session_id)
        elif request.operation == "save":
            result = service.save_session(request.session_id, request.data)
        else:
            raise ValueError("Invalid operation")
        return Response(success=True, data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/sessions")
async def list_sessions():
    """列出所有会话"""
    try:
        service = MemoryService()
        sessions = service.list_sessions()
        return Response(success=True, data=sessions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/tools")
async def list_tools():
    """列出可用工具"""
    try:
        service = AgentService()
        tools = service.list_tools()
        return Response(success=True, data=tools)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 标书审核API端点
# ==========================================

@router.post("/tender/create", response_model=Response)
async def tender_create(request: TenderCreateRequest):
    """创建标书审核任务"""
    try:
        service = get_tender_service()
        task = service.create_task(
            project_name=request.effective_project_name,
            project_type=request.effective_project_type,
            company_name=request.effective_company_name,
        )
        return Response(success=True, data=task.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tender/upload/{task_id}/{file_type}", response_model=Response)
async def tender_upload(task_id: str, file_type: str, file: UploadFile = File(...)):
    """上传标书文件
    file_type: tender (招标书) 或 bid (投标书)
    """
    try:
        if file_type not in ["tender", "bid"]:
            raise HTTPException(status_code=400, detail="file_type must be 'tender' or 'bid'")

        service = get_tender_service()
        file_bytes = await file.read()
        success = service.upload_file(
            task_id=task_id,
            file_type=file_type,
            file_bytes=file_bytes,
            filename=file.filename or "unknown.pdf",
        )
        if not success:
            raise HTTPException(status_code=404, detail="Task not found or upload failed")

        task = service.get_task(task_id)
        return Response(success=True, data=task.to_dict() if task else None)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tender/audit", response_model=Response)
async def tender_audit(request: TenderAuditRequest, background_tasks: BackgroundTasks):
    """启动标书审核流程"""
    try:
        service = get_tender_service()
        task = service.get_task(request.effective_task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        background_tasks.add_task(service.run_audit, request.effective_task_id, request.effective_use_mock)

        task.status = TaskStatus.PENDING
        task.message = "审核任务已提交，等待处理..."
        task.updated_at = task.updated_at

        return Response(success=True, data=task.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tender/status/{task_id}", response_model=Response)
async def tender_status(task_id: str):
    """查询审核任务状态"""
    try:
        service = get_tender_service()
        task = service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return Response(success=True, data=task.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tender/report/{task_id}", response_model=Response)
async def tender_report(task_id: str):
    """获取审核报告"""
    try:
        service = get_tender_service()
        task = service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        report = service.get_report(task_id)
        markdown = service.get_report_markdown(task_id)

        return Response(success=True, data={
            "task": task.to_dict(),
            "report": report,
            "markdown": markdown,
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tender/download/{task_id}")
async def tender_download(task_id: str, format: str = "json"):
    """下载审核报告
    format: json, md, html
    """
    try:
        service = get_tender_service()
        content, filename = service.download_report(task_id, format)
        if not content:
            raise HTTPException(status_code=404, detail="Report not found")

        media_types = {
            "json": "application/json",
            "md": "text/markdown; charset=utf-8",
            "html": "text/html; charset=utf-8",
        }

        return StreamingResponse(
            io.BytesIO(content),
            media_type=media_types.get(format, "application/octet-stream"),
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
