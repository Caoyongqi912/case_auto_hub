"""interface_executor.py 单测覆盖率补充 (目标 0% -> 60%+)。"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from croe.interface.executor.interface_executor import (
    InterfaceExecutor,
    ExecutionContext,
)
from enums import (
    InterfaceResponseStatusCodeEnum,
    InterfaceRequestMethodEnum,
)

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _build_interface(
    interface_id=1,
    uid="abc123",
    name="api",
    desc="d",
    method="GET",
    body_type=None,
    body=None,
    headers=None,
    params=None,
    data=None,
    env_id=1,
    before_params=None,
    before_script=None,
    before_sql=None,
    before_db_id=None,
    extracts=None,
    asserts=None,
    auth_type=None,
    auth=None,
    raw_type=None,
):
    iface = MagicMock()
    iface.id = interface_id
    iface.uid = uid
    iface.interface_name = name
    iface.interface_desc = desc
    iface.interface_method = method
    iface.interface_body_type = body_type
    iface.interface_body = body
    iface.interface_headers = headers
    iface.interface_params = params
    iface.interface_data = data
    iface.interface_auth_type = auth_type
    iface.interface_auth = auth
    iface.interface_raw_type = raw_type
    iface.interface_before_params = before_params
    iface.interface_before_script = before_script
    iface.interface_before_sql = before_sql
    iface.interface_before_db_id = before_db_id
    iface.interface_before_sql_extracts = None
    iface.interface_extracts = extracts
    iface.interface_asserts = asserts
    iface.env_id = env_id
    return iface

def _build_env(env_id=1, name="test_env", url="http://example.com"):
    env = MagicMock()
    env.id = env_id
    env.name = name
    env.url = url
    return env

def _build_starter(user_id=10, username="alice"):
    s = MagicMock()
    s.userId = user_id
    s.username = username
    s.send = AsyncMock()
    return s

def _build_variable_manager():
    mgr = MagicMock()
    mgr.trans = AsyncMock(side_effect=lambda x: x)
    mgr.add_vars = AsyncMock()
    mgr.variables = []
    return mgr

def _build_response(status=200, text='{"ok":true}', elapsed_ms=10):
    """Mock 一个 httpx.Response, 用真实 Response 不行 (需要 url+content)."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.text = text
    resp.headers = {"content-type": "application/json"}
    # elapsed 是 timedelta-like, 用 MagicMock 给 .total_seconds()
    resp.elapsed = MagicMock()
    resp.elapsed.total_seconds = MagicMock(return_value=elapsed_ms / 1000)
    return resp

def _build_executor(starter=None, var_mgr=None, g_headers=None):
    if starter is None:
        starter = _build_starter()
    if var_mgr is None:
        var_mgr = _build_variable_manager()
    # 绕开 __init__ 里 HttpxClient 实例化, 直接 patch http
    executor = InterfaceExecutor.__new__(InterfaceExecutor)
    executor.variable_manager = var_mgr
    executor.starter = starter
    executor.http = MagicMock()
    executor.http.close = AsyncMock()
    executor.g_headers = g_headers or []
    return executor

# --------------------------------------------------------------------------- #
# 1) __init__: global_headers=None 兜底
# --------------------------------------------------------------------------- #

@pytest.mark.unit
def test_init_global_headers_none_defaults_to_empty_list():
    """__init__: global_headers=None 时 g_headers 应兜底成 [], 不让 None 满天飞。"""
    starter = _build_starter()
    var_mgr = _build_variable_manager()
    with patch("croe.interface.executor.interface_executor.HttpxClient"):
        executor = InterfaceExecutor(starter=starter, variable_manager=var_mgr, global_headers=None)
    assert executor.g_headers == []
    assert executor.starter is starter
    assert executor.variable_manager is var_mgr

@pytest.mark.unit
def test_init_global_headers_passed_through():
    """__init__: global_headers=[...] 透传。"""
    starter = _build_starter()
    var_mgr = _build_variable_manager()
    g_headers = [MagicMock(), MagicMock()]
    with patch("croe.interface.executor.interface_executor.HttpxClient"):
        executor = InterfaceExecutor(starter=starter, variable_manager=var_mgr, global_headers=g_headers)
    assert executor.g_headers is g_headers

# --------------------------------------------------------------------------- #
# 2) execute 正常路径: 200 OK
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_execute_success_path_returns_result_dict_with_result_true():
    """execute 正常路径: mock httpx 返 200, asserts 走通 -> result['result']=True。"""
    executor = _build_executor()
    iface = _build_interface(extracts=None, asserts=None)
    env = _build_env()

    response = _build_response(status=200, text='{"hello":"world"}', elapsed_ms=42)
    # mock 整个 httpx 链路
    with patch(
        "croe.interface.executor.interface_executor.UrlBuilder.build",
        new=AsyncMock(return_value="http://example.com/api/v1/x"),
    ), patch(
        "croe.interface.executor.interface_executor.RequestBuilder"
    ) as mock_builder_cls, patch(
        "croe.interface.executor.interface_executor.AssertManager"
    ) as mock_assert_cls, patch(
        "croe.interface.executor.interface_executor.ExtractManager"
    ):
        mock_builder = MagicMock()
        mock_builder.set_req_info = AsyncMock(return_value={"headers": {}, "params": None})
        mock_builder_cls.return_value = mock_builder

        mock_assert_cls.return_value = AsyncMock(return_value=None)

        executor.http = AsyncMock(return_value=response)
        executor.http.close = AsyncMock()

        result = await executor.execute(interface=iface, env=env)

    # 正常路径 -> result=True, response_status=200
    assert result["result"] is True
    assert result["response_status"] == 200
    assert result["response_text"] == '{"hello":"world"}'
    assert result["interface_id"] == 1
    assert result["starter_id"] == 10
    assert result["starter_name"] == "alice"
    assert result["running_env_id"] == env.id
    assert result["running_env_name"] == env.name
    assert result["request_url"] == "http://example.com/api/v1/x"
    # asserts / extracts 过滤 None 后应为空 list
    assert result["asserts"] == []
    assert result["extracts"] == []
    # starter.send 至少被调一次 (EXECUTE API 起始日志)
    assert executor.starter.send.await_count >= 1

# --------------------------------------------------------------------------- #
# 3) execute ctx.error 路径: URLBuilder.build 抛异常 -> error 分支
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_execute_error_path_records_ctx_error_and_returns_failure():
    """execute 异常路径: build raise -> ctx.error 填上, _build_result 走 error 分支。
    锁定     """
    executor = _build_executor()
    iface = _build_interface(extracts=None, asserts=None)
    env = _build_env()

    with patch(
        "croe.interface.executor.interface_executor.UrlBuilder.build",
        new=AsyncMock(side_effect=ValueError("未提供环境配置")),
    ):
        result = await executor.execute(interface=iface, env=env)

    # error 分支: result=False, response_status=500, response_text=错误信息
    assert result["result"] is False
    assert result["response_status"] == 500
    assert "未提供环境配置" in result["response_text"]
    assert result["use_time"] == "0"
    # starter.send 至少 2 次: EXECUTE API + Error occurred
    send_msgs = [c.args[0] for c in executor.starter.send.call_args_list]
    assert any("EXECUTE API" in m for m in send_msgs)
    assert any("Error occurred" in m for m in send_msgs)

# --------------------------------------------------------------------------- #
# 4) execute 500 失败路径: 响应状态码 500 -> success=False
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_execute_500_status_marks_result_false():
    """execute 500 响应: 不走 error 分支, 走正常响应分支, 但 status_code != 200 -> success=False。"""
    executor = _build_executor()
    iface = _build_interface()
    env = _build_env()

    response = _build_response(status=500, text="Internal Server Error")

    with patch(
        "croe.interface.executor.interface_executor.UrlBuilder.build",
        new=AsyncMock(return_value="http://example.com/api"),
    ), patch(
        "croe.interface.executor.interface_executor.RequestBuilder"
    ) as mock_builder_cls, patch(
        "croe.interface.executor.interface_executor.AssertManager"
    ) as mock_assert_cls, patch(
        "croe.interface.executor.interface_executor.ExtractManager"
    ):
        mock_builder = MagicMock()
        mock_builder.set_req_info = AsyncMock(return_value={"headers": {}})
        mock_builder_cls.return_value = mock_builder
        mock_assert_cls.return_value = AsyncMock(return_value=None)

        executor.http = AsyncMock(return_value=response)

        result = await executor.execute(interface=iface, env=env)

    # 500 -> result=False
    assert result["result"] is False
    assert result["response_status"] == 500
    assert result["response_text"] == "Internal Server Error"
    # error 字段没填, 不应被填充
    assert result["use_time"] != "0"

# --------------------------------------------------------------------------- #
# 5) execute 断言失败: asserts 包含 result=False -> success=False
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_execute_assertion_failure_marks_result_false():
    """execute 断言失败: AssertManager 返含 result=False 的 asserts -> result['result']=False。
    锁定     """
    executor = _build_executor()
    iface = _build_interface(asserts=[{"key": "status", "value": 200, "assertOpt": 0}])
    env = _build_env()

    response = _build_response(status=200)
    failed_asserts = [{"key": "status", "result": False, "expected": 200, "actual": 500}]

    with patch(
        "croe.interface.executor.interface_executor.UrlBuilder.build",
        new=AsyncMock(return_value="http://example.com/api"),
    ), patch(
        "croe.interface.executor.interface_executor.RequestBuilder"
    ) as mock_builder_cls, patch(
        "croe.interface.executor.interface_executor.AssertManager"
    ) as mock_assert_cls, patch(
        "croe.interface.executor.interface_executor.ExtractManager"
    ):
        mock_builder = MagicMock()
        mock_builder.set_req_info = AsyncMock(return_value={"headers": {}})
        mock_builder_cls.return_value = mock_builder
        mock_assert_cls.return_value = AsyncMock(return_value=failed_asserts)

        executor.http = AsyncMock(return_value=response)

        result = await executor.execute(interface=iface, env=env)

    # 断言失败 -> result=False
    assert result["result"] is False
    assert result["response_status"] == 200
    assert result["asserts"] == failed_asserts

# --------------------------------------------------------------------------- #
# 6) _execute_before_params 3 分支
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_execute_before_params_none_returns_empty_list():
    """_execute_before_params: before_params=None -> [] (line 197-198 早返)。"""
    executor = _build_executor()
    result = await executor._execute_before_params(None)
    assert result == []
    executor.variable_manager.add_vars.assert_not_called()

@pytest.mark.asyncio
@pytest.mark.unit
async def test_execute_before_params_empty_list_returns_empty_list():
    """_execute_before_params: before_params=[] -> [] (空列表, falsy 早返)。"""
    executor = _build_executor()
    result = await executor._execute_before_params([])
    assert result == []

@pytest.mark.asyncio
@pytest.mark.unit
async def test_execute_before_params_values_adds_and_tags():
    """_execute_before_params: 有值时 trans + add_vars + 标记 source=BeforeParams。"""
    executor = _build_executor()
    executor.variable_manager.trans = AsyncMock(return_value=[{"key": "u", "value": "alice"}])

    result = await executor._execute_before_params([{"key": "u", "value": "alice"}])

    # 标记 source 后返 [{key, value, target=BeforeParams}]
    assert len(result) == 1
    assert result[0]["key"] == "u"
    assert result[0]["value"] == "alice"
    from enums import ExtractTargetVariablesEnum
    assert result[0][ExtractTargetVariablesEnum.Target] == ExtractTargetVariablesEnum.BeforeParams
    executor.variable_manager.add_vars.assert_awaited_once()

# --------------------------------------------------------------------------- #
# 7) _execute_before_script 2 分支
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_execute_before_script_none_returns_empty_list():
    """_execute_before_script: script=None -> 早返 []。"""
    executor = _build_executor()
    result = await executor._execute_before_script(None)
    assert result == []

@pytest.mark.asyncio
@pytest.mark.unit
async def test_execute_before_script_with_value_marks_before_script_source():
    """_execute_before_script: 脚本返 {k:v} dict -> 标记 source=BeforeScript。"""
    executor = _build_executor()
    with patch("croe.interface.executor.interface_executor.ScriptManager") as mock_sm_cls:
        mock_sm = MagicMock()
        mock_sm.execute = MagicMock(return_value={"token": "abc123"})
        mock_sm_cls.return_value = mock_sm

        result = await executor._execute_before_script("return {'token': 'abc123'}")

    from enums import ExtractTargetVariablesEnum
    assert len(result) == 1
    assert result[0][ExtractTargetVariablesEnum.KEY] == "token"
    assert result[0][ExtractTargetVariablesEnum.VALUE] == "abc123"
    assert result[0][ExtractTargetVariablesEnum.Target] == ExtractTargetVariablesEnum.BeforeScript
    executor.variable_manager.add_vars.assert_awaited_once()

# --------------------------------------------------------------------------- #
# 8) _execute_before_sql 2 分支
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_execute_before_sql_none_returns_empty_list():
    """_execute_before_sql: sql=None 或 db_id=None -> 早返 []。"""
    executor = _build_executor()
    iface = _build_interface(before_sql=None, before_db_id=None)
    result = await executor._execute_before_sql(iface)
    assert result == []

@pytest.mark.asyncio
@pytest.mark.unit
async def test_execute_before_sql_db_config_not_found_warns_and_returns_empty():
    """_execute_before_sql: db_config 不存在 -> starter.send 警告 + 返 []。"""
    executor = _build_executor()
    iface = _build_interface(before_sql="SELECT 1", before_db_id=999)

    with patch(
        "croe.interface.executor.interface_executor.DbConfigMapper.get_by_id",
        new=AsyncMock(return_value=None),
    ):
        result = await executor._execute_before_sql(iface)

    assert result == []
    # starter.send 收到了 db 不存在警告
    send_msgs = [c.args[0] for c in executor.starter.send.call_args_list]
    assert any("数据库配置不存在" in m for m in send_msgs)

# --------------------------------------------------------------------------- #
# 9) _execute_extract: 非 200 状态码早返
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_execute_extract_non_200_skips_extraction():
    """_execute_extract: response.status_code != 200 -> 早返 [], 不调 ExtractManager。"""
    executor = _build_executor()
    iface = _build_interface(extracts=[{"key": "x", "value": "$.x", "extraOpt": "jsonpath"}])
    response = _build_response(status=500)

    with patch("croe.interface.executor.interface_executor.ExtractManager") as mock_em_cls:
        result = await executor._execute_extract(response, iface)

    assert result == []
    # ExtractManager 不应被实例化
    mock_em_cls.assert_not_called()

@pytest.mark.asyncio
@pytest.mark.unit
async def test_execute_extract_no_extracts_returns_empty():
    """_execute_extract: interface_extracts=None/[] -> 早返 []。"""
    executor = _build_executor()
    iface = _build_interface(extracts=None)
    response = _build_response(status=200)

    result = await executor._execute_extract(response, iface)
    assert result == []

# --------------------------------------------------------------------------- #
# 10) _build_result: env=None 时 env_id 兜底
# --------------------------------------------------------------------------- #

@pytest.mark.unit
def test_build_result_env_none_falls_back_to_interface_env_id():
    """_build_result: ctx.env=None -> running_env_id 走 interface.env_id 兜底 (line 425-429)。"""
    executor = _build_executor()
    iface = _build_interface(env_id=42)
    response = _build_response(status=200)

    ctx = ExecutionContext(
        interface=iface,
        env=None,
        start_time="2026-06-20 10:00:00",
        resolved_url="http://x/api",
        response=response,
    )
    ctx.asserts = []
    ctx.extracted_vars = []

    result = executor._build_result(ctx)

    # env=None -> running_env_id 应兜底成 interface.env_id (42)
    assert result["running_env_id"] == 42
    # 'name' 不应设
    assert "running_env_name" not in result
    assert result["result"] is True

@pytest.mark.unit
def test_build_result_env_set_uses_env_id_and_name():
    """_build_result: ctx.env 有值 -> running_env_id 走 env.id, name 走 env.name。"""
    executor = _build_executor()
    iface = _build_interface(env_id=42)
    env = _build_env(env_id=99, name="dev")
    response = _build_response(status=200)

    ctx = ExecutionContext(
        interface=iface, env=env, start_time="t", resolved_url="u", response=response,
    )

    result = executor._build_result(ctx)

    assert result["running_env_id"] == 99  # env.id 覆盖 interface.env_id
    assert result["running_env_name"] == "dev"

# --------------------------------------------------------------------------- #
# 11) _normalize_temp_variables 3 分支 + aclose
# --------------------------------------------------------------------------- #

@pytest.mark.unit
def test_normalize_temp_variables_none_returns_empty_list():
    assert InterfaceExecutor._normalize_temp_variables(None) == []

@pytest.mark.unit
def test_normalize_temp_variables_list_passthrough():
    assert InterfaceExecutor._normalize_temp_variables([{"k": "v"}]) == [{"k": "v"}]

@pytest.mark.unit
def test_normalize_temp_variables_dict_wrapped_in_list():
    assert InterfaceExecutor._normalize_temp_variables({"k": "v"}) == [{"k": "v"}]

@pytest.mark.asyncio
@pytest.mark.unit
async def test_aclose_calls_http_close():
    """aclose: 释放 httpx client。锁定 BUG-E1。"""
    executor = _build_executor()
    await executor.aclose()
    executor.http.close.assert_awaited_once()

@pytest.mark.asyncio
@pytest.mark.unit
async def test_aclose_no_http_attribute_does_not_raise():
    """aclose: getattr http=None 兜底, 不抛 AttributeError。"""
    executor = _build_executor()
    # 模拟 __init__ 失败中途状态: 没有 http 属性
    del executor.http
    # 不应 raise
    await executor.aclose()
