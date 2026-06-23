"""request_builder.py 边角覆盖率补充 (目标 69% -> 80%+)。"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from croe.interface.builder.request_builder import (
    RequestBuilder,
    KEY_HEADERS,
    KEY_PARAMS,
    KEY_FORM_DATA,
    KEY_FORM_FILES,
)
from enums import (
    InterfaceAuthType,
    InterfaceDataValueType,
    InterfaceRequestMethodEnum,
    InterfaceRequestTBodyTypeEnum,
)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _build_interface(
    method="GET",
    body_type=None,
    headers=None,
    params=None,
    body=None,
    data=None,
    auth_type=InterfaceAuthType.No_Auth,
    auth=None,
    raw_type=None,
    connect_timeout=10,
    response_timeout=30,
    follow_redirects=False,
):
    iface = MagicMock()
    iface.interface_method = method
    iface.interface_body_type = body_type
    iface.interface_headers = headers or []
    iface.interface_params = params
    iface.interface_body = body
    iface.interface_data = data
    iface.interface_auth_type = auth_type
    iface.interface_auth = auth or {}
    iface.interface_raw_type = raw_type
    iface.interface_connect_timeout = connect_timeout
    iface.interface_response_timeout = response_timeout
    iface.interface_follow_redirects = follow_redirects
    return iface


def _builder():
    var_mgr = MagicMock()
    var_mgr.trans = MagicMock(side_effect=lambda x: x)
    return RequestBuilder(variables=var_mgr, global_headers=[])


# --------------------------------------------------------------------------- #
# 1) set_req_info 主流程 — GET 端到端
#    (line 76-102)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_set_req_info_get_end_to_end_main_flow():
    """set_req_info 主流程: GET + params + headers + No_Auth 全跑通。
    锁定 4 步流程 (init / params / auth / transform) 串起来。
    """
    builder = _builder()
    iface = _build_interface(
        method=InterfaceRequestMethodEnum.GET,
        headers=[{"key": "X-Api", "value": "v1"}],
        params=[{"key": "q", "value": "hello"}],
        connect_timeout=5,
        response_timeout=15,
        follow_redirects=True,
    )

    request_data = await builder.set_req_info(iface)

    # 1) 基础字段
    assert request_data["connect"] == 5
    assert request_data["read"] == 15
    assert request_data["follow_redirects"] is True
    # 2) headers
    assert request_data[KEY_HEADERS]["X-Api"] == "v1"
    # 3) GET params
    assert request_data[KEY_PARAMS] == {"q": "hello"}
    # 4) No_Auth: 不应加 Authorization
    assert "Authorization" not in request_data[KEY_HEADERS]


# --------------------------------------------------------------------------- #
# 1.5) _transform_request_data 不替换 httpx 配置字段
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_transform_request_data_skips_non_data_fields():
    """_transform_request_data 不应替换 timeout / connect / follow_redirects 等配置字段。"""
    builder = _builder()

    request_data = {
        KEY_HEADERS: {"X-Api": "{{api_version}}"},
        "url": "http://example.com/{{path}}",
        "read": 30,
        "connect": 10,
        "follow_redirects": True,
    }

    # 让 trans 把任何字符串都替换成 "REPLACED"
    builder.variables.trans = MagicMock(return_value="REPLACED")

    builder._transform_request_data(request_data)

    # 数据字段被替换
    assert request_data[KEY_HEADERS] == "REPLACED"
    assert request_data["url"] == "REPLACED"
    # 配置字段保持原值
    assert request_data["read"] == 30
    assert request_data["connect"] == 10
    assert request_data["follow_redirects"] is True


# --------------------------------------------------------------------------- #
# 2) KV Auth 三分支
#    (line 174-187)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_prepare_auth_kv_auth_to_query():
    """KV Auth target=query: kv 字段加到 params, target 字段被 pop 掉。"""
    builder = _builder()
    request_data = {KEY_PARAMS: {}, KEY_HEADERS: {}}
    # KVAuth Pydantic model 字典化后形如 {"key": "<实际字段名>", "value": "<实际值>", "target": "query"/"header"}
    iface = _build_interface(
        auth_type=InterfaceAuthType.KV_Auth,
        auth={"key": "api_key", "value": "abc123", "target": "query"},
    )

    await RequestBuilder._prepare_auth(request_data, iface)

    # target 字段已被 pop, 剩 key/value 被 list2dict 翻成 {"api_key": "abc123"}
    assert request_data[KEY_PARAMS] == {"api_key": "abc123"}
    # target 字段已被 pop, 不应出现在 query 里
    assert "target" not in request_data[KEY_PARAMS]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_prepare_auth_kv_auth_to_header():
    """KV Auth target=header: kv 字段加到 headers。"""
    builder = _builder()
    request_data = {KEY_PARAMS: {}, KEY_HEADERS: {}}
    iface = _build_interface(
        auth_type=InterfaceAuthType.KV_Auth,
        auth={"key": "X-Sign", "value": "sig-value", "target": "header"},
    )

    await RequestBuilder._prepare_auth(request_data, iface)

    assert request_data[KEY_HEADERS] == {"X-Sign": "sig-value"}


@pytest.mark.asyncio
@pytest.mark.unit
async def test_prepare_auth_kv_auth_unknown_target_logs_warning_bug_rb1():
    """[    """
    from tests.croe.interface._bug_ids import BUG_RB1
    builder = _builder()
    request_data = {KEY_PARAMS: {}, KEY_HEADERS: {}}
    iface = _build_interface(
        auth_type=InterfaceAuthType.KV_Auth,
        auth={"key": "X-Token", "value": "t1", "target": "body"},
    )
    iface.interface_case_id = 1234

    with patch("croe.interface.builder.request_builder.log") as mock_log:
        await RequestBuilder._prepare_auth(request_data, iface)

    mock_log.warning.assert_called_once()
    warn_msg = mock_log.warning.call_args.args[0]
    assert BUG_RB1 in warn_msg
    assert "'body'" in warn_msg
    assert "query / header" in warn_msg
    assert "case_id=1234" in warn_msg
    # 不抛异常, 且 request_data 仍未被污染
    assert request_data[KEY_PARAMS] == {}
    assert request_data[KEY_HEADERS] == {}


# --------------------------------------------------------------------------- #
# 3) _process_get_params 无 params
#    (line 217-220)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_process_get_params_no_params_key_unchanged():
    """_process_get_params: interface.interface_params=None, 不应给 request_data 加 KEY_PARAMS。"""
    builder = _builder()
    request_data = {KEY_HEADERS: {}}
    iface = _build_interface(method=InterfaceRequestMethodEnum.GET, params=None)

    await RequestBuilder._process_get_params(request_data, iface)

    assert KEY_PARAMS not in request_data


@pytest.mark.asyncio
@pytest.mark.unit
async def test_process_get_params_empty_list_unchanged():
    """_process_get_params: interface.interface_params=[] (空列表, falsy),
    不会进 if 分支, KEY_PARAMS 不被设。"""
    builder = _builder()
    request_data = {KEY_HEADERS: {}}
    iface = _build_interface(method=InterfaceRequestMethodEnum.GET, params=[])

    await RequestBuilder._process_get_params(request_data, iface)

    # [] 是 falsy, 跳过整个 if 分支, KEY_PARAMS 不设
    assert KEY_PARAMS not in request_data


# --------------------------------------------------------------------------- #
# 4) _filter_request_body 不支持的 body_type
#    (line 277-278)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_filter_request_body_unsupported_returns_none_none():
    """_filter_request_body: 未知 body_type -> log.warning + return (None, None)。
    锁住: 不支持的 type 不能让 set_req_info 崩。
    """
    builder = _builder()
    iface = _build_interface(body_type="UNKNOWN_TYPE")
    iface.interface_body = "x"

    with patch("croe.interface.builder.request_builder.log") as mock_log:
        body_data, content_type = await builder._filter_request_body(iface)

    assert body_data is None
    assert content_type is None
    mock_log.warning.assert_called_once()
    assert "不支持的请求体类型" in mock_log.warning.call_args.args[0]


# --------------------------------------------------------------------------- #
# 5) _prepare_form_data value_type=file
#    (line 356-363)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_prepare_form_data_file_record_not_found_skipped():
    """_prepare_form_data: value_type=file 但 FileMapper.get_by_uid 返 None -> 跳过。
    锁定: file_record 为空时, files dict 不应有这个 key, 也不应抛异常。
    """
    builder = _builder()
    iface = _build_interface(data=[
        {"key": "upload", "value": "missing-uid", "value_type": InterfaceDataValueType.FILE},
        {"key": "name", "value": "alice", "value_type": InterfaceDataValueType.TEXT},
    ])

    with patch(
        "croe.interface.builder.request_builder.FileMapper.get_by_uid",
        new=AsyncMock(return_value=None),
    ):
        result, content_type = await builder._prepare_form_data(iface)

    # files 不应有 "upload" key
    assert "upload" not in result[KEY_FORM_FILES]
    # text 类型正常进 data
    assert result[KEY_FORM_DATA] == {"name": "alice"}
    # 多部分表单 httpx 自动设 Content-Type, 应返 None
    assert content_type is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_prepare_form_data_file_record_found_calls_prepare_file_upload(tmp_path):
    """_prepare_form_data: value_type=file 且 file_record 存在 -> 调 _prepare_file_upload。
    锁定: 真实文件被读 + 放进 files dict。
    """
    builder = _builder()
    # 写个临时文件
    test_file = tmp_path / "hello.txt"
    test_file.write_bytes(b"file-content-bytes")

    fake_record = MagicMock()
    fake_record.file_path = str(test_file)
    fake_record.file_name = "hello.txt"
    fake_record.file_type = "text/plain"

    iface = _build_interface(data=[
        {"key": "upload", "value": "file-uid-1", "value_type": InterfaceDataValueType.FILE},
    ])

    with patch(
        "croe.interface.builder.request_builder.FileMapper.get_by_uid",
        new=AsyncMock(return_value=fake_record),
    ):
        result, _ = await builder._prepare_form_data(iface)

    # files["upload"] = (filename, bytes, mime)
    assert "upload" in result[KEY_FORM_FILES]
    filename, content, mime = result[KEY_FORM_FILES]["upload"]
    assert filename == "hello.txt"
    assert content == b"file-content-bytes"
    assert mime == "text/plain"


# --------------------------------------------------------------------------- #
# 6) _prepare_file_upload 4 个错误路径
#    (line 391-412)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_prepare_file_upload_file_not_exists_returns_none():
    """_prepare_file_upload: 文件不存在 -> log.error + return None。"""
    with patch("os.path.exists", return_value=False), \
         patch("croe.interface.builder.request_builder.log") as mock_log:
        result = await RequestBuilder._prepare_file_upload(
            "/nonexistent/path.txt", "x.txt", "text/plain"
        )
    assert result is None
    mock_log.error.assert_called_once()
    assert "文件不存在" in mock_log.error.call_args.args[0]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_prepare_file_upload_file_not_readable_returns_none():
    """_prepare_file_upload: 文件存在但不可读 -> log.error + return None。"""
    with patch("os.path.exists", return_value=True), \
         patch("os.access", return_value=False), \
         patch("croe.interface.builder.request_builder.log") as mock_log:
        result = await RequestBuilder._prepare_file_upload(
            "/some/path.txt", "x.txt", "text/plain"
        )
    assert result is None
    mock_log.error.assert_called_once()
    assert "文件不可读" in mock_log.error.call_args.args[0]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_prepare_file_upload_empty_file_returns_none():
    """_prepare_file_upload: 文件存在可读但内容为空 -> log.error + return None。"""
    fake_file = AsyncMock()
    fake_file.read = AsyncMock(return_value=b"")

    with patch("os.path.exists", return_value=True), \
         patch("os.access", return_value=True), \
         patch("aiofiles.open") as mock_open, \
         patch("croe.interface.builder.request_builder.log") as mock_log:
        mock_open.return_value.__aenter__ = AsyncMock(return_value=fake_file)
        mock_open.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await RequestBuilder._prepare_file_upload(
            "/some/empty.txt", "empty.txt", "text/plain"
        )
    assert result is None
    mock_log.error.assert_called_once()
    assert "无法读取文件内容" in mock_log.error.call_args.args[0]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_prepare_file_upload_aiofiles_raises_returns_none():
    """_prepare_file_upload: aiofiles.open 抛异常 -> log.exception + return None。
    锁定: 异常路径不阻塞, return None 让上层跳过这个 file。
    """
    with patch("os.path.exists", return_value=True), \
         patch("os.access", return_value=True), \
         patch("aiofiles.open", side_effect=OSError("disk error")), \
         patch("croe.interface.builder.request_builder.log") as mock_log:
        result = await RequestBuilder._prepare_file_upload(
            "/some/path.txt", "x.txt", "text/plain"
        )
    assert result is None
    # log.exception (比 error 多堆栈)
    mock_log.exception.assert_called_once()
    assert "处理文件" in mock_log.exception.call_args.args[0]
