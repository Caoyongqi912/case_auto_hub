import asyncio
import uuid
from typing import Dict, Any

from sse_starlette.sse import EventSourceResponse
from asyncio import Queue


class SSE:

    def __init__(self):
        self.subscribers: Dict[str, Queue] = {}

    async def subscriber(self, client_id: str):
        """订阅"""
        q = Queue(maxsize=10)

        self.subscribers[client_id] = q
        return q

    async def unsubscribe(self, client_id: str):
        """取消订阅"""
        if client_id in self.subscribers:
            del self.subscribers[client_id]

    async def publish(self, data: dict[str, Any], event_type: str = "ssh_messages"):
        """
        推送消息
        :param data:
        :param event_type:
        :return:
        """

        message = {
            "event": event_type,
            "data": data,
            "id": str(uuid.uuid4()),
            "retry": 3000  # 重连时间（毫秒）
        }

        disconnected = []
        for client, q in self.subscribers.items():
            try:
                await q.put(message)
            except Exception:
                disconnected.append(client)

        # 清理断开连接的客户端
        for client_id in disconnected:
            await self.unsubscribe(client_id)

    async def publish_to_client(self, client_id: str, data: dict, event_type: str = "ssh_messages"):
        """发布消息给指定客户端"""
        if client_id in self.subscribers:
            message = {
                "event": event_type,
                "data": data,
                "id": str(uuid.uuid4())
            }
            try:
                await self.subscribers[client_id].put(message)
            except Exception:
                await self.unsubscribe(client_id)


# 最简单的 SSE 管理器
class SimpleSSE:
    def __init__(self):
        self.user_queues = {}

    async def connect_user(self, user_id: str):
        """用户连接"""
        if user_id not in self.user_queues:
            self.user_queues[user_id] = asyncio.Queue()
        return self.user_queues[user_id]

    async def send_to_user(self, user_id: str, message: str):
        """发送消息给用户"""
        if user_id in self.user_queues:
            queue = self.user_queues[user_id]
            await queue.put(message)


sse = SimpleSSE()
# sse = SSE()
