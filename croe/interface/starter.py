#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/12/6
# @Author : cyq
# @File : io_sender
# @Software: PyCharm
# @Desc:

from typing import Union

from app.model.base import User
from enums import StarterEnum
from utils import GenerateTools, MyLoguru
from utils.io_sender import SocketSender

log = MyLoguru().get_logger()

Event = "api_message"
NS = "/api_namespace"


class STARTER_MSG_TYPE:
    """starter.send 消息类型枚举。

    字段:
      - EMOJI: 旧 emoji 协议 (DEPRECATED, 仅作 fallback 兼容前端)
      - BRACKET: 新结构化 [TYPE_xxx] 前缀 (推荐新代码使用)

    用法:
      await self.starter.send_typed(STARTER_MSG_TYPE.EXTRACT, \"变量 x = 1\")
      → \"[TYPE_EXTRACT] 变量 x = 1\"
    """
    # 旧 emoji 协议 (DEPRECATED, 保留兼容前端)
    EXECUTE = "✍️✍️"        # EXECUTE_API / EXECUTE_STEP / 步骤执行
    EXTRACT = "🫳🫳"         # 提取变量 / 响应参数 / 脚本变量
    SKIP = "⏭️⏭️"           # 跳过步骤
    FINISH = "✍️✍️"         # (跟 EXECUTE 复用, 完成时再带 FINISH 字样)
    ERROR = "❌"            # 错误 (SQL 执行失败等)

    # 新结构化协议 (推荐)
    TYPE_EXECUTE = "[TYPE_EXECUTE]"
    TYPE_EXTRACT = "[TYPE_EXTRACT]"
    TYPE_SKIP = "[TYPE_SKIP]"
    TYPE_FINISH = "[TYPE_FINISH]"
    TYPE_ERROR = "[TYPE_ERROR]"
    TYPE_INFO = "[TYPE_INFO]"


class APIStarter(SocketSender):
    """API启动器，用于发送API执行消息。
"""

    uid: str = None
    userId: int = None

    def __init__(self, user: Union[User, StarterEnum]):
        """
        初始化API启动器

        Args:
            user: 用户对象或启动器枚举
        """
        self.logs = []
        super().__init__(event=Event, user=user, ns=NS)

    async def send(self, msg: str) -> None:
        """
        异步发送消息方法

        推荐用 `send_typed(type, msg)` 走结构化类型, 旧版仅作 fallback
        兼容前端 (前端解析 emoji 协议时仍可工作)。

        Args:
            msg: 需要发送的消息内容

        Returns:
            无返回值
        """
        try:
            formatted_msg = f"{GenerateTools.getTime(1)} 🚀 🚀  {msg}"
            return await super().send(formatted_msg)
        except Exception as e:
            log.error(f"发送消息失败: {e}")

    async def send_typed(self, msg_type: str, msg: str) -> None:
        """
        发送结构化类型消息

        Args:
            msg_type: STARTER_MSG.TYPE_* 之一
            msg: 消息内容

        用法:
            await self.starter.send_typed(STARTER_MSG_TYPE.TYPE_EXTRACT, f"变量 = {vars}")
        """
        await self.send(f"{msg_type} {msg}")
