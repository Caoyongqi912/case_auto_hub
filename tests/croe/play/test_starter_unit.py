"""
croe.play.starter.UIStarter 单测覆盖

目标: 锁定 UIStarter 的 event / ns 常量 + send 行为。
- UIStarter 继承 SocketSender,使用固定 event="ui_message",ns="/ui_namespace"
- send 内部 catch 异常 (不抛) + 添加 timestamp 前缀 + 🤖 🤖 emoji
"""
import pytest
from unittest.mock import AsyncMock, patch

from enums.TaskEnum import StarterEnum
from app.model.base import User


def _make_user(uid="u-1", user_id=10, username="alice"):
    user = User()
    user.uid = uid
    user.id = user_id
    user.username = username
    return user


class TestUIStarterConstants:
    """UIStarter 模块常量: 防误改。"""

    def test_event_constant(self):
        from croe.play.starter import Event
        assert Event == "ui_message"

    def test_namespace_constant(self):
        from croe.play.starter import NS
        assert NS == "/ui_namespace"


class TestUIStarterInit:
    """UIStarter 构造: 调用 SocketSender.__init__ 并固定 event/ns。"""

    def test_inherits_socket_sender(self):
        from croe.play.starter import UIStarter
        from utils.io_sender import SocketSender
        assert issubclass(UIStarter, SocketSender)

    def test_init_stores_user(self):
        from croe.play.starter import UIStarter
        user = _make_user(username="bob")
        starter = UIStarter(user=user)
        assert starter.user is user

    def test_init_with_user_sets_uid(self):
        from croe.play.starter import UIStarter
        user = _make_user(uid="u-x", user_id=1, username="x")
        starter = UIStarter(user=user)
        assert starter.uid == "u-x"
        assert starter.userId == 1
        assert starter.starterName == "x"

    def test_init_with_starter_enum(self):
        from croe.play.starter import UIStarter
        starter = UIStarter(user=StarterEnum.Celery)
        assert starter.startBy == StarterEnum.Celery.value

    def test_init_uses_fixed_event(self):
        from croe.play.starter import UIStarter
        starter = UIStarter(user=_make_user())
        assert starter._event == "ui_message"

    def test_init_uses_fixed_ns(self):
        from croe.play.starter import UIStarter
        starter = UIStarter(user=_make_user())
        assert starter._ns == "/ui_namespace"

    def test_init_logs_empty(self):
        from croe.play.starter import UIStarter
        starter = UIStarter(user=_make_user())
        assert starter.logs == []


class TestUIStarterSend:
    """UIStarter.send: 加时间戳 + 🤖 emoji + 转发到 SocketSender.send。"""

    @pytest.mark.asyncio
    async def test_send_calls_super_with_timestamp_prefix(self):
        """业务约定: send 走 SocketSender.send,msg 会被加 [时间] 🤖 🤖  前缀。"""
        from croe.play.starter import UIStarter
        with patch("utils.io_sender.async_io") as mock_io:
            mock_io.emit = AsyncMock()
            starter = UIStarter(user=_make_user(uid="u-1"))
            await starter.send("开始执行")
        mock_io.emit.assert_awaited_once()
        data_payload = mock_io.emit.await_args.kwargs["data"]["data"]
        # 前缀应包含 🤖 emoji + 时间戳 (GenerateTools.getTime(1) 的输出)
        assert "🤖" in data_payload
        assert "开始执行" in data_payload

    @pytest.mark.asyncio
    async def test_send_uses_ui_namespace(self):
        """UIStarter 必须用 /ui_namespace,不能跟其他业务串。"""
        from croe.play.starter import UIStarter
        with patch("utils.io_sender.async_io") as mock_io:
            mock_io.emit = AsyncMock()
            starter = UIStarter(user=_make_user())
            await starter.send("x")
        assert mock_io.emit.await_args.kwargs["namespace"] == "/ui_namespace"

    @pytest.mark.asyncio
    async def test_send_event_is_ui_message(self):
        from croe.play.starter import UIStarter
        with patch("utils.io_sender.async_io") as mock_io:
            mock_io.emit = AsyncMock()
            starter = UIStarter(user=_make_user())
            await starter.send("x")
        assert mock_io.emit.await_args.kwargs["event"] == "ui_message"

    @pytest.mark.asyncio
    async def test_send_swallows_exception(self):
        """即使 super().send 内部抛,UIStarter.send 也不应向上抛。"""
        from croe.play.starter import UIStarter
        with patch("utils.io_sender.async_io") as mock_io:
            mock_io.emit = AsyncMock(side_effect=RuntimeError("boom"))
            starter = UIStarter(user=_make_user())
            # 不应抛
            await starter.send("any msg")

    @pytest.mark.asyncio
    async def test_send_with_empty_msg(self):
        """边界: 空字符串 msg 也应不抛。"""
        from croe.play.starter import UIStarter
        with patch("utils.io_sender.async_io") as mock_io:
            mock_io.emit = AsyncMock()
            starter = UIStarter(user=_make_user())
            await starter.send("")
        mock_io.emit.assert_awaited_once()


class TestUIStarterOver:
    """UIStarter.over: 继承自 SocketSender.over,code=1 信号。"""

    @pytest.mark.asyncio
    async def test_over_emits_code_1(self):
        from croe.play.starter import UIStarter
        with patch("utils.io_sender.async_io") as mock_io:
            mock_io.emit = AsyncMock()
            starter = UIStarter(user=_make_user())
            await starter.over(reportId=42)
        kwargs = mock_io.emit.await_args.kwargs
        assert kwargs["data"]["code"] == 1
        assert kwargs["data"]["data"]["rId"] == 42

    @pytest.mark.asyncio
    async def test_over_uses_ui_namespace(self):
        from croe.play.starter import UIStarter
        with patch("utils.io_sender.async_io") as mock_io:
            mock_io.emit = AsyncMock()
            starter = UIStarter(user=_make_user())
            await starter.over(1)
        assert mock_io.emit.await_args.kwargs["namespace"] == "/ui_namespace"


class TestUIStarterClearLogs:
    """UIStarter.clear_logs: 继承自 SocketSender。"""

    @pytest.mark.asyncio
    async def test_clear_logs(self):
        from croe.play.starter import UIStarter
        with patch("utils.io_sender.async_io") as mock_io:
            mock_io.emit = AsyncMock()
            starter = UIStarter(user=_make_user())
            await starter.send("a")
            assert len(starter.logs) == 1
            await starter.clear_logs()
            assert starter.logs == []
