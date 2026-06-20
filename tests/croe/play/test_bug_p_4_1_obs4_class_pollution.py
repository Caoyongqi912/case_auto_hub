"""OBS-4 测试改 SocketSender.send 类属性污染的回归测试。"""
import inspect
import os
from unittest.mock import AsyncMock, MagicMock, patch

from utils.io_sender import SocketSender

def _is_async_send():
    """验证 SocketSender.send 是 async 协程函数 (非 Mock)。"""
    raw = SocketSender.__dict__.get("send")
    if raw is None:
        return False
    # 排除 MagicMock/AsyncMock (它们的 type 名带 Mock)
    cls_name = type(raw).__name__
    if "Mock" in cls_name:
        return False
    return inspect.iscoroutinefunction(raw)

def test_p_4_1_socket_sender_send_is_async_coroutine():
    """基线: 在没有任何 patch 的情况下, SocketSender.send 必须是 async 协程函数。"""
    assert _is_async_send(), (
        "[BUG-P-4-1] SocketSender.send 已被污染成非 async 协程"
    )

def test_p_4_1_patch_object_temporary_replaces_and_restores():
    """[
    用 MagicMock 替换 (不是 AsyncMock), 避免 iscoroutinefunction 误判。
    """
    with patch.object(SocketSender, "send", MagicMock()):
        # patch 期间 send 已被替换成 MagicMock
        raw = SocketSender.__dict__.get("send")
        assert raw is not None
        assert not _is_async_send(), "patch 期间应已被替换成非协程"

    # patch 退出后, send 必须还原成原 coroutine
    assert _is_async_send(), (
        "[BUG-P-4-1] patch.object 退出后 SocketSender.send 未还原, "
        "说明测试在用类似 `__bases__[0].send = ...` 的污染写法"
    )

def test_p_4_1_obs4_test_source_no_longer_uses_bases_pollution():
    """[
    实现: 去掉注释行 + 去掉字符串字面量, 再 grep 是否还有 `__bases__[0].send = `。
    """
    obs4_path = os.path.join(
        os.path.dirname(__file__),
        "..", "interface", "test_bug_d10_e11_obs_4_5_6.py",
    )
    raw = open(obs4_path).read()

    # 去掉 # 注释和空行, 避免误命中 docstring / 注释里的描述
    code_lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # 简单去除行内注释 (粗略, 不完美)
        if "#" in line:
            in_str = False
            quote = None
            for i, ch in enumerate(line):
                if ch in ('"', "'") and (i == 0 or line[i-1] != "\\"):
                    if in_str and ch == quote:
                        in_str = False
                    elif not in_str:
                        in_str = True
                        quote = ch
                elif ch == "#" and not in_str:
                    line = line[:i]
                    break
        if "__bases__[0].send = " in line:
            code_lines.append(line)

    assert not code_lines, (
        f"[BUG-P-4-1] OBS-4 测试还在用 `__bases__[0].send =` 污染类属性 "
        f"(命中 {len(code_lines)} 行), 应改成 `with patch.object(SocketSender, 'send', ...)` 临时改:\n"
        + "\n".join(code_lines)
    )

def test_p_4_1_socket_sender_send_signature_unchanged():
    """[BUG-P-4-1] SocketSender.send 应是 `async def send(self, msg: str)`, 签名不能被改。"""
    sig = inspect.signature(SocketSender.send)
    params = list(sig.parameters.keys())
    assert params == ["self", "msg"], (
        f"[BUG-P-4-1] SocketSender.send 签名变了: {params}"
    )

def test_p_4_1_socket_sender_has_no_mock_in_dict():
    """[BUG-P-4-1] SocketSender.__dict__ 里不能有 Mock 类型的 send。"""
    raw = SocketSender.__dict__.get("send")
    if raw is not None:
        cls_name = type(raw).__name__
        assert "Mock" not in cls_name, (
            f"[BUG-P-4-1] SocketSender.__dict__['send'] 是 {cls_name}, "
            "说明之前有测试改了类属性没还原"
        )
