"""
[OBS-1 + OBS-2 + OBS-3] 可观测性基础设施回归测试。

OBS-1 失败链路 trace 不可达: runner / executor 异常分支只 log.exception,
  不写 step_result。修法不在本测试范围 (那是 InterfaceExecutor 改造),
  本测试只覆盖 OBS-2/3 的基础设施层。

OBS-2 缺 correlation id: 多 case 并发时日志无法拼出"哪条 case 跑的"。
  修法: contextvars 注入 trace_id, 跨 async / loguru / runner 一致。

OBS-3 缺 log 脱敏: URL/变量写进 log, 可能含 token / 密钥。
  修法: loguru patcher 在 emit 前 redact 敏感字段 (Authorization /
  Set-Cookie / Password / Token / api_key / secret 等)。

测试覆盖 (不接 DB, 用 loguru 临时 sink 抓 log):
  - trace_id 生命周期 (new / set / get / clear)
  - trace_id 跨 async Task 边界传递 (contextvars)
  - trace_id 注入 loguru output (patcher)
  - 敏感字段名识别 (10+ patterns)
  - redact_dict 深拷贝递归
  - redact_message 字符串模式 (key=value / key:value / "key": "value")
  - loguru patcher 端到端 (logger.info 触发 redact + trace_id 注入)
  - MyLoguru 装 patcher 后格式含 trace=
  - runner.run_interface_case 入口 set + finally clear
"""
import asyncio
import inspect

import pytest
from loguru import logger

from croe.interface.observability import (
    REDACTED,
    SENSITIVE_KEY_PATTERNS,
    _is_sensitive_key,
    _redact_message,
    clear_trace_id,
    get_trace_id,
    install_patchers,
    new_trace_id,
    redact_dict,
    set_trace_id,
)
from tests.croe.interface._bug_ids import BUG_OBS_1, BUG_OBS_2, BUG_OBS_3


# ---- helpers ----

@pytest.fixture(autouse=True)
def reset_trace_id():
    """每个测试前后清掉 trace_id, 避免污染。"""
    clear_trace_id()
    yield
    clear_trace_id()


@pytest.fixture
def capture_loguru():
    """抓 loguru 输出 (message 字段)。"""
    captured = []

    def sink(message):
        record = message.record
        captured.append({
            "message": record["message"],
            "extra": dict(record["extra"]),
        })

    handler_id = logger.add(sink, level="DEBUG", format="{message}")
    # 装 patchers, 让 trace_id / redact 生效
    install_patchers(logger)
    yield captured
    logger.remove(handler_id)


# ---- OBS-2: trace_id 生命周期 ----

@pytest.mark.unit
def test_bug_obs_2_trace_id_8_chars():
    """[BUG-OBS-2] new_trace_id 必须 8 字符 (够区分并发, 短, 不抢眼)。"""
    tid = new_trace_id()
    assert len(tid) == 8, f"trace_id 应 8 字符, 实际 {len(tid)}: {tid!r}"
    # 必须是 hex
    int(tid, 16)


@pytest.mark.unit
def test_bug_obs_2_trace_id_set_get_clear():
    """[BUG-OBS-2] set_trace_id / get_trace_id / clear_trace_id 生命周期。"""
    assert get_trace_id() is None, "初始必须 None"

    tid = set_trace_id()
    assert get_trace_id() == tid, f"set 后 get 应一致: {tid} != {get_trace_id()}"
    assert len(tid) == 8

    # 设一个已知的
    set_trace_id("abc12345")
    assert get_trace_id() == "abc12345"

    clear_trace_id()
    assert get_trace_id() is None, "clear 后必须 None"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_obs_2_trace_id_crosses_async_task_boundary():
    """[BUG-OBS-2] trace_id 跨 asyncio.Task 边界 (contextvars 核心卖点)。"""
    tid = set_trace_id("parent01")

    async def child_task():
        # 子 task 继承父 contextvars
        return get_trace_id()

    # 显式 ctx 拷贝 (Python 3.7+ asyncio 默认就这么做, 但显式一遍更稳)
    child_tid = await asyncio.create_task(child_task())
    assert child_tid == "parent01", (
        f"[{BUG_OBS_2}] 子 task 应继承父 trace_id, 实际 {child_tid!r}"
    )

    # 主 task 仍是 parent01
    assert get_trace_id() == "parent01"

    # 子 task 改自己的不影响主
    async def child_set():
        set_trace_id("child99")
        return get_trace_id()

    child_tid2 = await asyncio.create_task(child_set())
    assert child_tid2 == "child99"
    assert get_trace_id() == "parent01", (
        f"[{BUG_OBS_2}] 子 task 改 trace_id 不影响主 task"
    )


# ---- OBS-3: 敏感字段识别 ----

@pytest.mark.unit
@pytest.mark.parametrize("key", [
    "Authorization",
    "authorization",
    "AUTHORIZATION",
    "Set-Cookie",
    "set-cookie",
    "Cookie",
    "cookie",
    "Password",
    "password",
    "passwd",
    "pass_word",
    "Token",
    "token",
    "TOKEN",
    "api_key",
    "ApiKey",
    "apikey",
    "access_key",
    "secret",
    "Secret",
    "x-auth-token",  # 复合: 包含 token
    "MyPasswordField",  # 复合: 包含 password
])
def test_bug_obs_3_sensitive_key_recognized(key):
    """[BUG-OBS-3] 10+ 模式: Authorization / Set-Cookie / Cookie / Password /
    passwd / pass_word / Token / api_key / access_key / secret 全识别 (大小写不敏感, 子串)。"""
    assert _is_sensitive_key(key), (
        f"[{BUG_OBS_3}] {key!r} 应识别为敏感, 但漏了"
    )


@pytest.mark.unit
@pytest.mark.parametrize("key", [
    "user",
    "email",
    "url",
    "method",
    "case_id",
    "Authorization_safe",  # 复合: 含 Authorization 但带 _safe 后缀? — 子串, 应识别
    "url_token_path",  # 复合: 包含 token
])
def test_bug_obs_3_safe_key_not_matched(key):
    """[BUG-OBS-3] 正常字段不应误识别。"""
    # 子串匹配, 所以 url_token_path / Authorization_safe 也算敏感
    # 这条测试是反面, 故意让用户知道子串匹配的代价
    if "token" in key.lower() or "password" in key.lower() or "auth" in key.lower():
        # 接受子串匹配的事实
        assert _is_sensitive_key(key)
    else:
        assert not _is_sensitive_key(key), (
            f"[{BUG_OBS_3}] {key!r} 不应识别为敏感, 但被误判"
        )


@pytest.mark.unit
def test_bug_obs_3_sensitive_patterns_count():
    """[BUG-OBS-3] SENSITIVE_KEY_PATTERNS 至少 10 个 pattern (防缩水)。"""
    assert len(SENSITIVE_KEY_PATTERNS) >= 10, (
        f"[{BUG_OBS_3}] 应至少 10 个 pattern, 实际 {len(SENSITIVE_KEY_PATTERNS)}"
    )


# ---- OBS-3: redact_dict ----

@pytest.mark.unit
def test_bug_obs_3_redact_dict_basic():
    """[BUG-OBS-3] redact_dict 把敏感字段值替换, 非敏感保留。"""
    red = redact_dict({
        "Authorization": "Bearer abc",
        "user": "alice",
        "url": "https://x.com",
    })
    assert red["Authorization"] == REDACTED
    assert red["user"] == "alice"
    assert red["url"] == "https://x.com"


@pytest.mark.unit
def test_bug_obs_3_redact_dict_nested():
    """[BUG-OBS-3] redact_dict 递归处理嵌套 dict。"""
    red = redact_dict({
        "headers": {"Authorization": "Bearer x", "Content-Type": "json"},
        "data": {"token": "abc", "user_id": 42},
    })
    assert red["headers"]["Authorization"] == REDACTED
    assert red["headers"]["Content-Type"] == "json"
    assert red["data"]["token"] == REDACTED
    assert red["data"]["user_id"] == 42


@pytest.mark.unit
def test_bug_obs_3_redact_dict_list():
    """[BUG-OBS-3] redact_dict 处理 list / tuple 内的 dict。"""
    red = redact_dict([
        {"Authorization": "a", "name": "first"},
        {"password": "p", "name": "second"},
    ])
    assert red[0]["Authorization"] == REDACTED
    assert red[0]["name"] == "first"
    assert red[1]["password"] == REDACTED
    assert red[1]["name"] == "second"


@pytest.mark.unit
def test_bug_obs_3_redact_dict_does_not_mutate_input():
    """[BUG-OBS-3] redact_dict 深拷贝, 不改原 obj。"""
    original = {"Authorization": "secret", "ok": 1}
    red = redact_dict(original)
    assert original["Authorization"] == "secret", (
        f"[{BUG_OBS_3}] redact_dict 不应改原 dict, 实际: {original}"
    )
    assert red["Authorization"] == REDACTED
    assert red is not original, "必须返新 dict"


# ---- OBS-3: redact_message ----

@pytest.mark.unit
@pytest.mark.parametrize("raw,expected_key_redacted", [
    ("Authorization=Bearer abc", True),
    ("authorization: bearer xyz", True),
    ("password=hunter2", True),
    ('"Authorization": "Bearer abc"', True),
    ("token=abc123", True),
    ("api_key=sk-12345", True),
    ("url=https://x.com user=alice", False),
    ("method=GET", False),
    ("case_id=42", False),
    ("no key value here", False),
])
def test_bug_obs_3_redact_message(raw, expected_key_redacted):
    """[BUG-OBS-3] redact_message 扫 key=value / key:value / 'key':'value' 模式。"""
    red = _redact_message(raw)
    if expected_key_redacted:
        assert REDACTED in red, (
            f"[{BUG_OBS_3}] 敏感字段应 redact, 实际: {red!r}"
        )
        # 原敏感值不在了
        assert "Bearer abc" not in red
        assert "hunter2" not in red
        assert "abc123" not in red
        assert "sk-12345" not in red
    else:
        assert red == raw, (
            f"[{BUG_OBS_3}] 正常字段应保留, 实际: {red!r} (原: {raw!r})"
        )


# ---- OBS-1 + OBS-3: loguru patcher 端到端 ----

@pytest.mark.unit
def test_bug_obs_2_3_patcher_injects_trace_id_in_log(capture_loguru):
    """[BUG-OBS-2] patcher 必须把 trace_id 注入到每条 log 的 extra.trace_id。"""
    set_trace_id("cafebabe")
    logger.info("hello world")

    assert len(capture_loguru) == 1
    record = capture_loguru[0]
    assert record["extra"].get("trace_id") == "cafebabe", (
        f"[{BUG_OBS_2}] patcher 应注入 trace_id, 实际: {record['extra']}"
    )


@pytest.mark.unit
def test_bug_obs_2_patcher_default_dash(capture_loguru):
    """[BUG-OBS-2] 没 set_trace_id 时, trace_id 默认 '-' (单测 / 脚本场景)。"""
    logger.info("hello")
    record = capture_loguru[0]
    assert record["extra"].get("trace_id") == "-", (
        f"[{BUG_OBS_2}] 默认应是 '-', 实际: {record['extra']}"
    )


@pytest.mark.unit
def test_bug_obs_3_patcher_redacts_message(capture_loguru):
    """[BUG-OBS-3] loguru message 里 Authorization=xxx 自动变 ***REDACTED***。"""
    logger.info("Authorization=Bearer abc123 url=https://x.com")
    record = capture_loguru[0]
    assert "***REDACTED***" in record["message"], (
        f"[{BUG_OBS_3}] message 应被 redact, 实际: {record['message']!r}"
    )
    assert "Bearer abc123" not in record["message"]
    # url 没影响
    assert "https://x.com" in record["message"]


@pytest.mark.unit
def test_bug_obs_3_patcher_redacts_dict_extra(capture_loguru):
    """[BUG-OBS-3] loguru extra=dict 里的敏感字段也自动 redact。

    loguru 把 **kwargs 当成 extra 字段, dict/list/tuple 走 redact 路径。
    """
    logger.info("calling api", headers={"Authorization": "Bearer xyz", "x-ok": "1"})
    record = capture_loguru[0]
    headers = record["extra"].get("headers")
    assert headers is not None, (
        f"[{BUG_OBS_3}] headers 应注入 extra, 实际: {record['extra']!r}"
    )
    assert headers["Authorization"] == REDACTED, (
        f"[{BUG_OBS_3}] extra dict 内的敏感字段应 redact, 实际: {headers!r}"
    )
    assert headers["x-ok"] == "1"


# ---- OBS-1: MyLoguru 装 patcher ----

@pytest.mark.unit
def test_bug_obs_1_myloguru_format_has_trace_id():
    """[BUG-OBS-1+2] MyLoguru 的日志格式必须含 {extra[trace_id]} (patcher 才有用)。"""
    from utils._myLoguru import MyLoguru
    # 直接读 _configure_logger 源码 (避免实际初始化写文件)
    src = inspect.getsource(MyLoguru._configure_logger)
    assert "{extra[trace_id]}" in src, (
        f"[{BUG_OBS_2}] MyLoguru base_format 必须含 {{extra[trace_id]}}, "
        f"否则 patcher 注入的 trace_id 显示不出来"
    )
    # 必须装 patcher
    assert "install_patchers" in src, (
        f"[{BUG_OBS_1}] MyLoguru 必须调 install_patchers, "
        f"否则 trace_id / redact 都不生效"
    )


# ---- OBS-2: runner 集成 ----

@pytest.mark.unit
def test_bug_obs_2_runner_run_interface_case_sets_trace_id():
    """[BUG-OBS-2] runner.run_interface_case 入口必须 set_trace_id()。"""
    from croe.interface.runner import InterfaceRunner
    src = inspect.getsource(InterfaceRunner.run_interface_case)
    assert "set_trace_id()" in src, (
        f"[{BUG_OBS_2}] run_interface_case 必须 set_trace_id(), "
        f"否则每条 case 没独立 correlation id"
    )


@pytest.mark.unit
def test_bug_obs_2_runner_finally_clears_trace_id():
    """[BUG-OBS-2] runner.run_interface_case 的 finally 必须 clear_trace_id()。"""
    from croe.interface.runner import InterfaceRunner
    src = inspect.getsource(InterfaceRunner.run_interface_case)
    # finally 块里必须有 clear_trace_id
    assert "clear_trace_id" in src, (
        f"[{BUG_OBS_2}] run_interface_case finally 必须 clear_trace_id(), "
        f"否则下条 case 复用上条的 trace_id, 串了"
    )


@pytest.mark.unit
def test_bug_obs_2_runner_first_log_has_trace_id():
    """[BUG-OBS-2] runner 第一条 log.info 必须显式带 trace_id 前缀,
    让运维 grep 时第一眼就拿到。"""
    from croe.interface.runner import InterfaceRunner
    src = inspect.getsource(InterfaceRunner.run_interface_case)
    # 期望 '查询到业务流用例' 这条 log 带 [trace=...]
    assert "查询到业务流用例" in src and "[trace=" in src, (
        f"[{BUG_OBS_2}] run_interface_case 第一条 log 应带 [trace=...] 前缀"
    )
