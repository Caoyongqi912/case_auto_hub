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


class APIStarter(SocketSender):
    """API启动器，用于发送API执行消息"""

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

        该方法负责格式化消息并将其发送给用户。它首先会尝试格式化消息，
        然后记录日志，保存消息记录，并通过异步I/O发送消息。如果在过程中
        出现任何异常，它会记录错误信息。

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
