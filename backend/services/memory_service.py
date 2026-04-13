"""
记忆服务 - 长短期记忆管理
"""

import json
import time
import redis
from typing import Dict, Any, Optional, List
from backend.config.settings import settings


class MemoryService:
    """记忆服务"""

    def __init__(self):
        self.memory_type = settings.memory.memory_type
        self.max_session_length = settings.memory.max_session_length
        self.session_ttl = settings.memory.session_ttl
        
        if self.memory_type == "redis":
            self.redis = redis.Redis(
                host=settings.redis.host,
                port=settings.redis.port,
                db=settings.redis.db,
                password=settings.redis.password,
                decode_responses=True
            )
        else:
            self.in_memory = {}

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """获取会话"""
        if self.memory_type == "redis":
            data = self.redis.get(f"session:{session_id}")
            if data:
                return json.loads(data)
        else:
            if session_id in self.in_memory:
                return self.in_memory[session_id]
        return {"messages": []}

    def save_session(self, session_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """保存会话"""
        session_data = self.get_session(session_id)
        
        if "messages" not in session_data:
            session_data["messages"] = []
        
        if "messages" in data:
            session_data["messages"].extend(data["messages"])
            
            # 限制会话长度
            if len(session_data["messages"]) > self.max_session_length:
                session_data["messages"] = session_data["messages"][-self.max_session_length:]
        
        session_data["updated_at"] = int(time.time())
        
        if self.memory_type == "redis":
            self.redis.setex(
                f"session:{session_id}",
                self.session_ttl,
                json.dumps(session_data)
            )
        else:
            self.in_memory[session_id] = session_data
        
        return session_data

    def clear_session(self, session_id: str) -> Dict[str, Any]:
        """清空会话"""
        if self.memory_type == "redis":
            self.redis.delete(f"session:{session_id}")
        else:
            if session_id in self.in_memory:
                del self.in_memory[session_id]
        return {"status": "cleared"}

    def list_sessions(self) -> List[str]:
        """列出所有会话"""
        if self.memory_type == "redis":
            keys = self.redis.keys("session:*")
            return [key.replace("session:", "") for key in keys]
        else:
            return list(self.in_memory.keys())

    def add_message(self, session_id: str, role: str, content: str) -> Dict[str, Any]:
        """添加消息"""
        session_data = self.get_session(session_id)
        
        message = {
            "role": role,
            "content": content,
            "timestamp": int(time.time())
        }
        
        if "messages" not in session_data:
            session_data["messages"] = []
        
        session_data["messages"].append(message)
        
        # 限制会话长度
        if len(session_data["messages"]) > self.max_session_length:
            session_data["messages"] = session_data["messages"][-self.max_session_length:]
        
        return self.save_session(session_id, session_data)

    def get_recent_messages(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的消息"""
        session_data = self.get_session(session_id)
        messages = session_data.get("messages", [])
        return messages[-limit:]

    def get_session_metadata(self, session_id: str) -> Dict[str, Any]:
        """获取会话元数据"""
        session_data = self.get_session(session_id)
        return {
            "session_id": session_id,
            "message_count": len(session_data.get("messages", [])),
            "updated_at": session_data.get("updated_at", 0),
            "created_at": session_data.get("created_at", session_data.get("updated_at", 0))
        }
