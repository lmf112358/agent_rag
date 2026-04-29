"""
API路由模块
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import io
from backend.services.rag_service import RAGService
from backend.services.memory_service import MemoryService
from backend.services.agent_service import AgentService
from backend.services.quote_service import QuoteAuditService
from backend.services.conversation_service import conversation_service
from backend.services.tender_service import (
    get_tender_service,
    TaskStatus,
)

router = APIRouter()

# 报价审核服务实例
quote_service = QuoteAuditService()


class QueryRequest(BaseModel):
    """查询请求"""
    query: str = Field(..., description="用户查询内容")
    session_id: Optional[str] = Field(None, description="会话ID")
    context: Optional[Dict[str, Any]] = Field(None, description="上下文信息")


class AgentRequest(BaseModel):
    """Agent请求"""
    query: str = Field(..., description="用户查询内容")
    session_id: Optional[str] = Field(None, description="会话ID")
    conversation_id: Optional[str] = Field(None, description="对话ID")
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
        
        # 如果提供了 conversation_id，保存消息到对话
        if request.conversation_id:
            conv = conversation_service.get_conversation(request.conversation_id)
            if not conv:
                # 对话不存在，创建它
                conv = conversation_service.create_conversation()
                conversation_service.add_message(
                    conv["id"], "user", request.query, use_markdown=False
                )
            else:
                conversation_service.add_message(
                    request.conversation_id, "user", request.query, use_markdown=False
                )
        
        result = service.invoke(
            query=request.query,
            session_id=request.session_id,
            tools=request.tools
        )
        
        # 如果有 conversation_id，也保存助手回复
        if request.conversation_id and result.get("answer"):
            conversation_service.add_message(
                request.conversation_id, "assistant", result.get("answer"), use_markdown=True
            )
        
        return Response(
            success=True,
            data=result,
            session_id=result.get("session_id"),
            conversation_id=request.conversation_id
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


# ------------------------------
# 报价审核相关API
# ------------------------------

class QuoteAuditRequest(BaseModel):
    """报价审核请求"""
    project_name: str = Field(..., description="项目名称")
    total_rt: Optional[float] = Field(None, description="项目制冷量（RT）")
    building_area: Optional[float] = Field(None, description="建筑面积（㎡）")


@router.post("/quote/audit", summary="执行报价审核")
async def quote_audit(
    file: UploadFile = File(...),
    project_name: str = Form(...),
    total_rt: Optional[float] = Form(None),
    building_area: Optional[float] = Form(None),
):
    """上传Excel并执行报价审核"""
    import shutil
    from pathlib import Path
    
    UPLOAD_DIR = Path("data/uploads")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        if not file.filename.endswith((".xlsx", ".xls")):
            raise HTTPException(status_code=400, detail="仅支持Excel文件")
        
        # 保存上传文件
        import uuid
        file_id = str(uuid.uuid4())
        file_path = UPLOAD_DIR / f"{file_id}_{file.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 执行审核
        result = quote_service.run_audit(
            excel_path=str(file_path),
            project_name=project_name,
            total_rt=total_rt,
            building_area=building_area,
        )
        
        # 清理临时文件
        if file_path.exists():
            file_path.unlink()
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return Response(
            success=True,
            data=result["report"],
            message="审核完成"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"审核失败：{str(e)}")

# ==========================================
# 对话管理API端点
# ==========================================

class ConversationCreateRequest(BaseModel):
    """创建对话请求"""
    title: Optional[str] = Field("新对话", description="对话标题")


class ConversationMessageRequest(BaseModel):
    """对话消息请求"""
    role: str = Field(..., description="消息角色: user 或 assistant")
    content: str = Field(..., description="消息内容")
    use_markdown: bool = Field(False, description="是否使用Markdown")


@router.get("/conversations", response_model=Response)
async def list_conversations():
    """列出所有对话"""
    try:
        conversations = conversation_service.list_conversations()
        return Response(success=True, data=conversations)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations", response_model=Response)
async def create_conversation(request: ConversationCreateRequest):
    """创建新对话"""
    try:
        conv = conversation_service.create_conversation(title=request.title or "新对话")
        return Response(success=True, data=conv)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}", response_model=Response)
async def get_conversation(conversation_id: str):
    """获取对话详情"""
    try:
        conv = conversation_service.get_conversation(conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="对话不存在")
        return Response(success=True, data=conv)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}/messages", response_model=Response)
async def get_conversation_messages(conversation_id: str):
    """获取对话消息列表"""
    try:
        messages = conversation_service.get_messages(conversation_id)
        return Response(success=True, data=messages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversations/{conversation_id}", response_model=Response)
async def delete_conversation(conversation_id: str):
    """删除对话"""
    try:
        success = conversation_service.delete_conversation(conversation_id)
        if not success:
            raise HTTPException(status_code=404, detail="对话不存在")
        return Response(success=True, data={"status": "deleted"})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations/{conversation_id}/messages", response_model=Response)
async def add_conversation_message(conversation_id: str, request: ConversationMessageRequest):
    """添加消息到对话"""
    try:
        conv = conversation_service.add_message(
            conversation_id,
            role=request.role,
            content=request.content,
            use_markdown=request.use_markdown
        )
        if not conv:
            raise HTTPException(status_code=404, detail="对话不存在")
        return Response(success=True, data=conv)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversations/{conversation_id}/messages", response_model=Response)
async def clear_conversation_messages(conversation_id: str):
    """清空对话消息"""
    try:
        success = conversation_service.clear_conversation(conversation_id)
        if not success:
            raise HTTPException(status_code=404, detail="对话不存在")
        return Response(success=True, data={"status": "cleared"})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
