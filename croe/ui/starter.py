from app.model.base import User
from enums import StarterEnum
from utils import MyLoguru, GenerateTools
from utils.io_sender import SocketSender

log = MyLoguru().get_logger()

Event = "ui_message"
NS = "/ui_namespace"


class UIStarter(SocketSender):

    def __init__(self, user: User | StarterEnum):
        super().__init__(event=Event, user=user, ns=NS)

    async def send(self, msg: str):
        try:
            # 格式化消息，添加时间戳。
            msg = f"{GenerateTools.getTime(1)} 🤖 🤖  {msg}"


            return await super().send(msg)
        except Exception as e:
            # 记录发送过程中出现的错误。
            log.error(e)
