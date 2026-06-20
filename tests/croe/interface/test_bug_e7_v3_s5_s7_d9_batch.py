"""[BUG-E7 + V3 + S5 + S7 + D9] 5 个 easy wins 回归测试。"""

import inspect
import json
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# ============================================================
# ============================================================

@pytest.mark.unit
def test_bug_e7_filter_none_in_asserts_and_extracts():
    """[BUG-E7] _build_result 必须过滤 None 项, 不留 [None] 给后续 JSON 序列化。"""
    from croe.interface.executor.interface_executor import InterfaceExecutor
    src = inspect.getsource(InterfaceExecutor._build_result)
    # 必须有 None 过滤
    assert "if v is not None" in src or "if a is not None" in src, (
        f"[BUG-E7] _build_result 必须过滤 None, 当前源码:\n{src[:500]}"
    )
    # 不应只有 `or []` (那个挡不住 [None]) 直接赋值给 result dict
    # 新的代码是 `[v for v in (ctx.extracted_vars or []) if v is not None]`
    # 所以 'or []' 在新代码里以 (xxx or []) 形式出现, 这是允许的
    # 关键是不能再有 'extracts': ctx.extracted_vars or [], 这种直接赋值
    assert "'extracts': ctx.extracted_vars or []" not in src, (
        f"[BUG-E7] 'extracts' 不应直接用 or [], 应改显式过滤 None 项"
    )
    assert "'asserts': ctx.asserts or []" not in src, (
        f"[BUG-E7] 'asserts' 不应直接用 or [], 应改显式过滤 None 项"
    )

# ============================================================
# ============================================================

@pytest.mark.unit
def test_bug_v3_script_manager_renamed_variables():
    """[BUG-V3] ScriptManager._variables 必须改名 _script_locals, 注释清楚语义。"""
    from croe.a_manager.script_manager import ScriptManager
    src = inspect.getsource(ScriptManager)
    # 旧的 _variables 必须没了
    assert "self._variables" not in src, (
        f"[BUG-V3] 旧 self._variables 还在, 应改 _script_locals, 实际 src 第一行:\n"
        f"{src[:300]}"
    )
    # 新的 _script_locals 必须在
    assert "self._script_locals" in src, (
        f"[BUG-V3] 新的 self._script_locals 必须有, 当前 src:\n{src[:300]}"
    )
@pytest.mark.unit
def test_bug_v3_hub_variables_methods_use_script_locals():
    """[BUG-V3] _hub_variables_set/get/remove 必须用 _script_locals。"""
    from croe.a_manager.script_manager import ScriptManager
    for name in ("_hub_variables_set", "_hub_variables_get", "_hub_variables_remove"):
        src = inspect.getsource(getattr(ScriptManager, name))
        assert "self._script_locals" in src, (
            f"[BUG-V3] {name} 必须用 self._script_locals, 实际: {src}"
        )
        assert "self._variables" not in src, (
            f"[BUG-V3] {name} 不应再用 self._variables, 实际: {src}"
        )

# ============================================================
# ============================================================

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_s5_raw_text_with_str_body_not_dumped():
    """[BUG-S5] raw text 模式 + body 是 str, 不应再走 json.dumps 加多余引号。"""
    from croe.interface.builder.request_builder import RequestBuilder

    iface = MagicMock()
    iface.interface_raw_type = "text"
    iface.interface_body = "hello {{user_name}}"  # 字符串, raw text

    body, ct = await RequestBuilder._prepare_raw_body(iface)
    assert ct == "text/plain"
    # body 应该是 {"content": "hello {{user_name}}"}, 不加引号
    assert body == {"content": "hello {{user_name}}"}, (
        f"[BUG-S5] raw text + str body 不应 json.dumps, 实际: {body!r}"
    )
    # 关键: 不应有外层 JSON 引号
    content_val = body["content"]
    assert not (content_val.startswith('"') and content_val.endswith('"')), (
        f"[BUG-S5] str body 不应被 json.dumps 包引号, 实际: {content_val!r}"
    )

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_s5_raw_text_with_dict_body_still_dumped():
    """[BUG-S5] raw text 模式 + body 是 dict, 仍应 json.dumps (用户显式选 dict)。"""
    from croe.interface.builder.request_builder import RequestBuilder

    iface = MagicMock()
    iface.interface_raw_type = "text"
    iface.interface_body = {"foo": "bar"}

    body, ct = await RequestBuilder._prepare_raw_body(iface)
    assert ct == "text/plain"
    # dict 走 json.dumps
    assert body == {"content": '{"foo": "bar"}'}, (
        f"[BUG-S5] dict body 应 json.dumps, 实际: {body!r}"
    )

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_s5_raw_text_str_with_backslashes_not_double_escaped():
    """[BUG-S5] raw text + str 含反斜杠, 不应被 double-escape。"""
    from croe.interface.builder.request_builder import RequestBuilder

    iface = MagicMock()
    iface.interface_raw_type = "text"
    iface.interface_body = "C:\\path\\to\\file"

    body, ct = await RequestBuilder._prepare_raw_body(iface)
    # 不应 double-escape: "C:\\path\\to\\file" -> "C:\\\\path\\\\to\\\\file" 是错的
    assert body["content"] == "C:\\path\\to\\file", (
        f"[BUG-S5] 反斜杠不应被 double-escape, 实际: {body!r}"
    )
    assert "\\\\" not in body["content"], (
        f"[BUG-S5] 不应出现 \\\\\\\\, 实际: {body!r}"
    )

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_s5_json_raw_type_unchanged():
    """[BUG-S5] json raw_type 走 KEY_JSON 不变 (回归保护)。"""
    from croe.interface.builder.request_builder import RequestBuilder

    iface = MagicMock()
    iface.interface_raw_type = "json"
    iface.interface_body = {"foo": "bar"}

    body, ct = await RequestBuilder._prepare_raw_body(iface)
    assert ct == "application/json"
    assert body == {"json": {"foo": "bar"}}, (
        f"[BUG-S5] json raw_type 应走 KEY_JSON 返原 dict, 实际: {body!r}"
    )

# ============================================================
# ============================================================

@pytest.mark.unit
def test_bug_s7_blocked_headers_constant_exists():
    """[BUG-S7] RequestBuilder 必有 BLOCKED_DOWNSTREAM_HEADERS 常量。"""
    from croe.interface.builder.request_builder import RequestBuilder
    assert hasattr(RequestBuilder, "BLOCKED_DOWNSTREAM_HEADERS"), (
        f"[BUG-S7] RequestBuilder 缺 BLOCKED_DOWNSTREAM_HEADERS"
    )
    blocked = RequestBuilder.BLOCKED_DOWNSTREAM_HEADERS
    # 至少拦 Host / Content-Length / Connection
    for h in ("host", "content-length", "connection"):
        assert h in blocked, (
            f"[BUG-S7] BLOCKED_DOWNSTREAM_HEADERS 必须含 {h!r}, 实际: {blocked}"
        )

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_s7_blocks_host_header_in_interface_headers():
    """[BUG-S7] 用户配 Host: malicious 必须被拦截, 不写进 headers。"""
    from croe.interface.builder.request_builder import RequestBuilder
    from app.model.interfaceAPIModel.interfaceModel import Interface

    rb = RequestBuilder(variables=MagicMock(), global_headers=None)

    # list2dict 接收 list[dict] 含 key/value, 不用 MagicMock
    iface = MagicMock(spec=Interface)
    iface.interface_headers = [
        {"key": "Host", "value": "evil.com"},
        {"key": "User-Agent", "value": "MyAgent"},
    ]

    headers = await rb._prepare_headers(iface)
    # Host 被拦, User-Agent 保留
    assert "Host" not in headers, (
        f"[BUG-S7] Host 必须被拦截, 实际 headers: {headers!r}"
    )
    assert "User-Agent" in headers
    assert headers["User-Agent"] == "MyAgent"

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_s7_blocks_content_length():
    """[BUG-S7] Content-Length 必须被拦截 (后端控制 body 大小, 用户不能改)。"""
    from croe.interface.builder.request_builder import RequestBuilder

    rb = RequestBuilder(variables=MagicMock(), global_headers=None)

    iface = MagicMock()
    iface.interface_headers = [
        {"key": "content-length", "value": "999999"},
        {"key": "X-Custom", "value": "ok"},
    ]

    headers = await rb._prepare_headers(iface)
    assert "content-length" not in headers
    assert "Content-Length" not in headers
    assert headers.get("X-Custom") == "ok"

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_s7_normal_headers_still_pass():
    """[BUG-S7] 正常 header (X-Custom / Authorization) 不应被误拦。"""
    from croe.interface.builder.request_builder import RequestBuilder

    rb = RequestBuilder(variables=MagicMock(), global_headers=None)

    iface = MagicMock()
    iface.interface_headers = [
        {"key": "Authorization", "value": "Bearer abc"},
        {"key": "X-Request-Id", "value": "12345"},
    ]

    headers = await rb._prepare_headers(iface)
    assert headers["Authorization"] == "Bearer abc"
    assert headers["X-Request-Id"] == "12345"

# ============================================================
# ============================================================

@pytest.mark.unit
def test_bug_n2_page_case_results_removed_after_d9():
    """[
    历史: D9 把 page_case_results 从 `pass` 改成 raise NotImplementedError 防静默吞错。
    N2 进一步发现这两个方法 0 caller, 是真正的 dead code, 直接删了最干净。
    替代方案: 分页走 list_by_filter + 分页参数, 查单个走 get_by_id (D9 注释里给过指引)。
    """
    from app.mapper.interfaceApi.interfaceResultMapper import InterfaceCaseResultMapper

    assert not hasattr(InterfaceCaseResultMapper, "page_case_results"), (
        "[BUG-N2] page_case_results 还在, 应该是 dead code 删了"
    )

@pytest.mark.unit
def test_bug_n2_query_case_result_removed_after_d9():
    """[BUG-D9 → BUG-N2] query_case_result dead code 已删 (理由同上)。"""
    from app.mapper.interfaceApi.interfaceResultMapper import InterfaceCaseResultMapper

    assert not hasattr(InterfaceCaseResultMapper, "query_case_result"), (
        "[BUG-N2] query_case_result 还在, 应该是 dead code 删了"
    )

@pytest.mark.unit
def test_bug_n2_no_plain_pass_in_d9_methods():
    """[BUG-N2] 旧 BUG-D9 关注点 (raise NotImplementedError) 已通过删除方法彻底解决。"""
    from app.mapper.interfaceApi.interfaceResultMapper import InterfaceCaseResultMapper

    for name in ("page_case_results", "query_case_result"):
        assert not hasattr(InterfaceCaseResultMapper, name), (
            f"[BUG-N2] {name} 应该被删 (N2 dead code 清理), 不应还在 mapper 上"
        )

