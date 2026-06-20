"""
utils.io_sender SocketSender 单测覆盖

目标: 锁定 SocketSender 的消息格式 + 异常兜底行为。
- send: 拼 {code:0, data:msg} + 走 async_io.emit
- over: 拼 {code:1, data:{rId:reportId}} 走 async_io.emit
- push: 走 /api_perf_ns 性能测试 namespace
- username: User 走 username / StarterEnum 走 name
- clear_logs: 重置日志列表
- send 异常: 内部吞掉 (不抛),记录 log

约定: 不连真实 ws, 全部 patch app.ws.async_io.emit
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from enums.TaskEnum import StarterEnum
from app.model.base import User


def _make_user(uid="u-1", user_id=10, username="alice"):
    """构造一个未持久化的 User 实例 (SQLAlchemy 允许裸构造,仅当 to_dict 才连 DB)。"""
    user = User()
    user.uid = uid
    user.id = user_id
    user.username = username
    return user


class TestSocketSenderInit:
    """SocketSender 构造期: 解析 user / 写 ns / 写 event。"""

    def test_init_with_user_sets_uid_and_userId(self):
        from utils.io_sender import SocketSender
        user = _make_user(uid="u-abc", user_id=42, username="bob")
        sender = SocketSender(ns="/ns", event="evt", user=user)
        assert sender.uid == "u-abc"
        assert sender.userId == 42
        assert sender.starterName == "bob"
        assert sender.startBy == StarterEnum.User.value

    def test_init_with_starter_enum_sets_start_by(self):
        """传 StarterEnum.Jenkins 时 startBy 应等于 Jenkins.value, uid/userId 留 None。"""
        from utils.io_sender import SocketSender
        sender = SocketSender(ns="/ns", event="evt", user=StarterEnum.Jenkins)
        assert sender.startBy == StarterEnum.Jenkins.value
        assert sender.uid is None
        assert sender.userId is None

    def test_init_initializes_empty_logs(self):
        from utils.io_sender import SocketSender
        sender = SocketSender(ns="/ns", event="evt", user=_make_user())
        assert sender.logs == []

    def test_event_and_ns_stored(self):
        from utils.io_sender import SocketSender
        sender = SocketSender(ns="/my_ns", event="my_evt", user=_make_user())
        assert sender._event == "my_evt"
        assert sender._ns == "/my_ns"

    def test_user_attribute_preserved(self):
        from utils.io_sender import SocketSender
        user = _make_user()
        sender = SocketSender(ns="/ns", event="evt", user=user)
        assert sender.user is user


class TestSocketSenderSend:
    """send: 格式化 + append log + emit。"""

    @pytest.mark.asyncio
    async def test_send_appends_msg_to_logs(self):
        from utils.io_sender import SocketSender
        with patch("utils.io_sender.async_io") as mock_io:
            mock_io.emit = AsyncMock()
            sender = SocketSender(ns="/ns", event="evt", user=_make_user())
            await sender.send("hello")
        assert len(sender.logs) == 1
        assert "hello" in sender.logs[0]

    @pytest.mark.asyncio
    async def test_send_calls_emit_with_code_0(self):
        """业务约定: send 发的是进行中消息,code=0,data=msg 字符串。"""
        from utils.io_sender import SocketSender
        with patch("utils.io_sender.async_io") as mock_io:
            mock_io.emit = AsyncMock()
            sender = SocketSender(ns="/ns", event="evt", user=_make_user(uid="u-1"))
            await sender.send("doing something")
        mock_io.emit.assert_awaited_once()
        kwargs = mock_io.emit.await_args.kwargs
        assert kwargs["event"] == "evt"
        assert kwargs["uid"] == "u-1"
        assert kwargs["namespace"] == "/ns"
        assert kwargs["data"]["code"] == 0
        assert "doing something" in kwargs["data"]["data"]

    @pytest.mark.asyncio
    async def test_send_swallows_exception(self):
        """send 出错时不应向上抛,只 log。"""
        from utils.io_sender import SocketSender
        with patch("utils.io_sender.async_io") as mock_io:
            mock_io.emit = AsyncMock(side_effect=RuntimeError("ws disconnected"))
            sender = SocketSender(ns="/ns", event="evt", user=_make_user())
            # 不应抛
            await sender.send("any msg")
        # 仍 append 了 (因为 log 在 try 内的 emit 之前)
        assert len(sender.logs) == 1

    @pytest.mark.asyncio
    async def test_send_uses_user_uid_when_user_provided(self):
        from utils.io_sender import SocketSender
        with patch("utils.io_sender.async_io") as mock_io:
            mock_io.emit = AsyncMock()
            sender = SocketSender(ns="/ns", event="evt", user=_make_user(uid="specific-uid"))
            await sender.send("x")
        assert mock_io.emit.await_args.kwargs["uid"] == "specific-uid"


class TestSocketSenderOver:
    """over: 报告结束信号,code=1, data 包含 rId。"""

    @pytest.mark.asyncio
    async def test_over_emits_code_1(self):
        from utils.io_sender import SocketSender
        with patch("utils.io_sender.async_io") as mock_io:
            mock_io.emit = AsyncMock()
            sender = SocketSender(ns="/ns", event="evt", user=_make_user())
            await sender.over(reportId=99)
        mock_io.emit.assert_awaited_once()
        kwargs = mock_io.emit.await_args.kwargs
        assert kwargs["data"]["code"] == 1
        assert kwargs["data"]["data"]["rId"] == 99

    @pytest.mark.asyncio
    async def test_over_accepts_none_reportId(self):
        from utils.io_sender import SocketSender
        with patch("utils.io_sender.async_io") as mock_io:
            mock_io.emit = AsyncMock()
            sender = SocketSender(ns="/ns", event="evt", user=_make_user())
            await sender.over()
        assert mock_io.emit.await_args.kwargs["data"]["data"]["rId"] is None

    @pytest.mark.asyncio
    async def test_over_accepts_string_reportId(self):
        from utils.io_sender import SocketSender
        with patch("utils.io_sender.async_io") as mock_io:
            mock_io.emit = AsyncMock()
            sender = SocketSender(ns="/ns", event="evt", user=_make_user())
            await sender.over(reportId="rpt-abc")
        assert mock_io.emit.await_args.kwargs["data"]["data"]["rId"] == "rpt-abc"

    @pytest.mark.asyncio
    async def test_over_swallows_exception(self):
        from utils.io_sender import SocketSender
        with patch("utils.io_sender.async_io") as mock_io:
            mock_io.emit = AsyncMock(side_effect=ConnectionError("lost"))
            sender = SocketSender(ns="/ns", event="evt", user=_make_user())
            # 不应抛
            await sender.over(1)


class TestSocketSenderPush:
    """push: 性能测试走 /api_perf_ns namespace。"""

    @pytest.mark.asyncio
    async def test_push_uses_perf_namespace(self):
        from utils.io_sender import SocketSender
        with patch("utils.io_sender.async_io") as mock_io:
            mock_io.emit = AsyncMock()
            sender = SocketSender(ns="/ns", event="evt", user=_make_user())
            await sender.push({"metric": "qps", "value": 100})
        assert mock_io.emit.await_args.kwargs["namespace"] == "/api_perf_ns"

    @pytest.mark.asyncio
    async def test_push_passes_data_through(self):
        from utils.io_sender import SocketSender
        with patch("utils.io_sender.async_io") as mock_io:
            mock_io.emit = AsyncMock()
            sender = SocketSender(ns="/ns", event="evt", user=_make_user())
            payload = {"k": "v"}
            await sender.push(payload)
        assert mock_io.emit.await_args.kwargs["data"] == payload

    @pytest.mark.asyncio
    async def test_push_swallows_exception(self):
        from utils.io_sender import SocketSender
        with patch("utils.io_sender.async_io") as mock_io:
            mock_io.emit = AsyncMock(side_effect=OSError("ws closed"))
            sender = SocketSender(ns="/ns", event="evt", user=_make_user())
            await sender.push({})


class TestSocketSenderUsername:
    """username property: User 走 username, StarterEnum 走 Enum.name。"""

    def test_username_returns_user_username(self):
        from utils.io_sender import SocketSender
        sender = SocketSender(ns="/ns", event="evt", user=_make_user(username="carol"))
        assert sender.username == "carol"

    def test_username_returns_enum_name_for_jenkins(self):
        from utils.io_sender import SocketSender
        sender = SocketSender(ns="/ns", event="evt", user=StarterEnum.Jenkins)
        assert sender.username == "Jenkins"

    def test_username_returns_enum_name_for_robot(self):
        from utils.io_sender import SocketSender
        sender = SocketSender(ns="/ns", event="evt", user=StarterEnum.RoBot)
        assert sender.username == "RoBot"

    def test_username_returns_enum_name_for_celery(self):
        from utils.io_sender import SocketSender
        sender = SocketSender(ns="/ns", event="evt", user=StarterEnum.Celery)
        assert sender.username == "Celery"


class TestSocketSenderClearLogs:
    """clear_logs: 重置日志列表。"""

    @pytest.mark.asyncio
    async def test_clear_logs_resets_to_empty(self):
        from utils.io_sender import SocketSender
        with patch("utils.io_sender.async_io") as mock_io:
            mock_io.emit = AsyncMock()
            sender = SocketSender(ns="/ns", event="evt", user=_make_user())
            await sender.send("a")
            await sender.send("b")
            assert len(sender.logs) == 2
            await sender.clear_logs()
            assert sender.logs == []

    @pytest.mark.asyncio
    async def test_clear_logs_on_empty_list_no_error(self):
        from utils.io_sender import SocketSender
        sender = SocketSender(ns="/ns", event="evt", user=_make_user())
        await sender.clear_logs()
        assert sender.logs == []


class TestSocketSenderConstants:
    """常量/类属性: 防误改。"""

    def test_perf_ns_constant(self):
        from utils.io_sender import SocketSender
        # 类属性,所有实例共享
        assert SocketSender._perf_ns == "/api_perf_ns"

    def test_uid_default_none_for_starter_enum(self):
        """StarterEnum 路径下,uid 留类属性默认 None (非实例属性)。"""
        from utils.io_sender import SocketSender
        sender = SocketSender(ns="/ns", event="evt", user=StarterEnum.Jenkins)
        # 走了 else 分支, 没设 self.uid
        assert sender.uid is None
