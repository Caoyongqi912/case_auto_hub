from typing import Union

from app.model.base import User
from enums import StarterEnum
from utils import MyLoguru
from app.ws import async_io

log = MyLoguru().get_logger()


class SocketSender:
    _event: str
    uid: str = None
    userId: int = None
    _ns: str = None
    _perf_ns = "/api_perf_ns"

    def __init__(self, ns: str, event: str, user: Union[User, StarterEnum]):
        self.user = user
        self._event = event
        self._ns = ns
        self.logs = []
        if isinstance(user, User):
            self.startBy = StarterEnum.User.value
            self.starterName = user.username
            self.uid = user.uid
            self.userId = user.id
        else:
            self.startBy = user.value

    async def send(self, msg: str):
        """
        异步发送消息方法。

        该方法负责格式化消息并将其发送给用户。它首先会尝试格式化消息，
        然后记录日志，保存消息记录，并通过异步I/O发送消息。如果在过程中
        出现任何异常，它会记录错误信息。

        参数:
        - msg (str): 需要发送的消息内容。

        返回:
        无返回值。
        """
        try:
            # 记录格式化后的消息。
            log.info(msg)
            # 将消息添加到日志列表中。
            self.logs.append(msg + "\n")

            # 准备发送的数据。
            data = {"code": 0, 'data': msg}
            # 使用异步I/O发送消息。
            await async_io.emit(event=self._event,
                                data=data,
                                uid=self.uid,
                                namespace=self._ns)

        except Exception as e:
            # 记录发送过程中出现的错误。
            log.error(e)

    async def over(self, reportId: int | str = None):
        try:
            data = {"code": 1, 'data': dict(rId=reportId)}
            await async_io.emit(event=self._event, data=data, uid=self.uid,
                                namespace=self._ns)
        except Exception as e:
            log.error(e)

    async def push(self, data: dict):
        """
        性能测试用
        异步发送data

        参数:
        - msg (dict): 需要发送的消息内容。
        返回:
        无返回值。
        """
        try:

            # 使用异步I/O发送消息。
            # 使用异步I/O发送消息。
            await async_io.emit(event=self._event,
                                data=data,
                                uid=self.uid,
                                namespace=self._perf_ns)
        except Exception as e:
            # 记录发送过程中出现的错误。
            log.error(e)

    @property
    def username(self):
        if self.startBy == StarterEnum.User.value:
            return self.starterName
        return StarterEnum(self.startBy).name

    async def clear_logs(self):
        self.logs = []
