"""
API路由模块
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from backend.services.rag_service import RAGService
from backend.services.memory_service import MemoryService
from backend.services.agent_service import AgentService

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
