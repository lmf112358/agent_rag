"""
对话服务 - 多对话管理
"""
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class ConversationService:
    """对话服务 - 管理多个对话会话"""

    _instance: Optional["ConversationService"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # 存储目录
        self.storage_dir = Path("data/conversations")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self._initialized = True
        print("[ConversationService] 初始化完成")

    def _get_conv_file(self, conv_id: str) -> Path:
        """获取对话文件路径"""
        return self.storage_dir / f"{conv_id}.json"

    def create_conversation(self, title: str = "新对话") -> Dict[str, Any]:
        """创建新对话"""
        import uuid
        conv_id = f"conv_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"

        conv_data = {
            "id": conv_id,
            "title": title,
            "messages": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        self._save_conversation(conv_id, conv_data)
        return conv_data

    def get_conversation(self, conv_id: str) -> Optional[Dict[str, Any]]:
        """获取对话"""
        file_path = self._get_conv_file(conv_id)
        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ConversationService] 读取对话失败: {e}")
            return None

    def update_conversation(self, conv_id: str, conv_data: Dict[str, Any]) -> bool:
        """更新对话"""
        conv_data["updated_at"] = datetime.now().isoformat()
        return self._save_conversation(conv_id, conv_data)

    def _save_conversation(self, conv_id: str, conv_data: Dict[str, Any]) -> bool:
        """保存对话到文件"""
        try:
            file_path = self._get_conv_file(conv_id)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(conv_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[ConversationService] 保存对话失败: {e}")
            return False

    def delete_conversation(self, conv_id: str) -> bool:
        """删除对话"""
        file_path = self._get_conv_file(conv_id)
        if file_path.exists():
            try:
                file_path.unlink()
                return True
            except Exception as e:
                print(f"[ConversationService] 删除对话失败: {e}")
                return False
        return True

    def list_conversations(self) -> List[Dict[str, Any]]:
        """列出所有对话（按更新时间倒序）"""
        conversations = []

        if not self.storage_dir.exists():
            return conversations

        for file_path in self.storage_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    conv_data = json.load(f)
                    conversations.append({
                        "id": conv_data.get("id"),
                        "title": conv_data.get("title", "未命名"),
                        "message_count": len(conv_data.get("messages", [])),
                        "created_at": conv_data.get("created_at"),
                        "updated_at": conv_data.get("updated_at")
                    })
            except Exception as e:
                print(f"[ConversationService] 读取对话列表失败: {e}")
                continue

        # 按更新时间倒序
        conversations.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return conversations

    def add_message(self, conv_id: str, role: str, content: str, use_markdown: bool = False) -> Optional[Dict[str, Any]]:
        """添加消息到对话"""
        conv_data = self.get_conversation(conv_id)
        if not conv_data:
            return None

        message = {
            "role": role,
            "content": content,
            "use_markdown": use_markdown,
            "timestamp": int(time.time())
        }

        conv_data["messages"].append(message)

        # 更新标题为第一条用户消息的前20个字符
        if role == "user" and len(conv_data["messages"]) == 1:
            conv_data["title"] = content[:20] + ("..." if len(content) > 20 else "")

        self.update_conversation(conv_id, conv_data)
        return conv_data

    def get_messages(self, conv_id: str) -> List[Dict[str, Any]]:
        """获取对话的所有消息"""
        conv_data = self.get_conversation(conv_id)
        if not conv_data:
            return []
        return conv_data.get("messages", [])

    def clear_conversation(self, conv_id: str) -> bool:
        """清空对话消息"""
        conv_data = self.get_conversation(conv_id)
        if not conv_data:
            return False

        conv_data["messages"] = []
        self.update_conversation(conv_id, conv_data)
        return True


# 全局单例
conversation_service = ConversationService()
