"""
request_builder.py 单测覆盖率补充 (目标 43% → 80%+)。

测 RequestBuilder 的 5 个核心方法:
1. _prepare_headers: g_headers + interface_headers merge + S7 黑名单拦截
2. _process_get_params: 变量替换 + 过滤空值
3. _process_request_body: 3 种 body type (Raw / UrlEncoded / Data)
4. _prepare_auth: 多种 auth type (No_Auth / Basic / Bearer)
5. _filter_request_body: 过滤空值
"""
from unittest.mock import MagicMock, patch

import pytest

from croe.interface.builder.request_builder import RequestBuilder
from enums import (
    InterfaceAuthType,
    InterfaceRequestTBodyTypeEnum,
)


def _build_interface(
    method="GET",
    body_type=None,
    headers=None,        # list of {"key": "k1", "value": "v1"} (GenerateTools.list2dict 格式)
    params=None,
    body=None,
    data=None,
    auth_type=InterfaceAuthType.No_Auth,
    auth=None,
    raw_type=None,
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
    return iface


def _build_global_headers(items):
    """items: list of (id, map_dict)"""
    out = []
    for hid, mp in items:
        h = MagicMock()
        h.id = hid
        h.map = mp
        out.append(h)
    return out


@pytest.fixture
def builder():
    var_mgr = MagicMock()
    var_mgr.trans = MagicMock(side_effect=lambda x: x)
    return RequestBuilder(variables=var_mgr, global_headers=[])


# --------------------------------------------------------------------------- #
# _prepare_headers
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_prepare_headers_merges_global_and_interface():
    """g_headers + interface_headers 应 merge, 后者覆盖前者。"""
    var_mgr = MagicMock()
    var_mgr.trans = MagicMock(side_effect=lambda x: x)
    g_headers = _build_global_headers([(1, {"X-Shared": "global_val", "X-Global": "1"})])
    builder = RequestBuilder(variables=var_mgr, global_headers=g_headers)

    # interface_headers 是 list of {"key": ..., "value": ...} (list2dict 格式)
    iface = _build_interface(headers=[
        {"key": "X-Custom", "value": "from_iface"},
        {"key": "X-Shared", "value": "iface_val"},
    ])
    iface.interface_case_id = 99

    result = await builder._prepare_headers(iface)
    assert result["X-Shared"] == "iface_val"  # interface 覆盖 global
    assert result["X-Global"] == "1"
    assert result["X-Custom"] == "from_iface"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_prepare_headers_blocks_sensitive_headers():
    """S7 黑名单: Host/Content-Length/Connection/Transfer-Encoding/Upgrade 被拦截。"""
    var_mgr = MagicMock()
    var_mgr.trans = MagicMock(side_effect=lambda x: x)
    builder = RequestBuilder(variables=var_mgr, global_headers=[])
    iface = _build_interface(headers=[
        {"key": "Host", "value": "evil.com"},
        {"key": "Content-Length", "value": "9999"},
        {"key": "Connection", "value": "close"},
        {"key": "Transfer-Encoding", "value": "chunked"},
        {"key": "Upgrade", "value": "h2c"},
        {"key": "X-OK", "value": "1"},
    ])
    iface.interface_case_id = 99

    with patch("croe.interface.builder.request_builder.log") as mock_log:
        result = await builder._prepare_headers(iface)
    assert "Host" not in result
    assert "Content-Length" not in result
    assert "Connection" not in result
    assert "Transfer-Encoding" not in result
    assert "Upgrade" not in result
    assert result["X-OK"] == "1"
    assert mock_log.warning.call_count == 5


@pytest.mark.asyncio
@pytest.mark.unit
async def test_prepare_headers_no_headers_no_global(builder):
    """g_headers + interface_headers 都空: 返空 dict。"""
    iface = _build_interface(headers=[])
    result = await builder._prepare_headers(iface)
    assert result == {}


# --------------------------------------------------------------------------- #
# _process_get_params
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_process_get_params_filters_empty(builder):
    """GET params 走 list2dict, 过滤空值 (变量替换在 set_req_info 主流程后做)。"""
    iface = _build_interface(params=[
        {"key": "k1", "value": "v1"},
        {"key": "k2", "value": ""},
        {"key": "k3", "value": None},
        {"key": "k4", "value": "v4"},
    ])
    request_data = {}

    await builder._process_get_params(request_data, iface)

    assert "params" in request_data
    params = request_data["params"]
    assert params.get("k1") == "v1"
    assert params.get("k4") == "v4"
    assert "k2" not in params
    assert "k3" not in params


# --------------------------------------------------------------------------- #
# _process_request_body 路由
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_process_request_body_raw_text(builder):
    """body_type=Raw + raw_type != json: 写入 'content'。"""
    iface = _build_interface(
        body_type=InterfaceRequestTBodyTypeEnum.Raw,
        raw_type="text",
        body="raw text",
    )
    request_data = {"headers": {}}
    await builder._process_request_body(request_data, iface)
    assert request_data.get("content") == "raw text"
    assert request_data["headers"].get("Content-Type") == "text/plain"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_process_request_body_raw_json(builder):
    """body_type=Raw + raw_type=json: 写入 'json' + Content-Type application/json。"""
    iface = _build_interface(
        body_type=InterfaceRequestTBodyTypeEnum.Raw,
        raw_type="json",
        body={"k": "v"},
    )
    request_data = {"headers": {}}
    await builder._process_request_body(request_data, iface)
    assert request_data.get("json") == {"k": "v"}
    assert request_data["headers"].get("Content-Type") == "application/json"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_process_request_body_urlencoded(builder):
    """body_type=UrlEncoded: 写入 'data' + Content-Type x-www-form-urlencoded。"""
    iface = _build_interface(
        body_type=InterfaceRequestTBodyTypeEnum.UrlEncoded,
        data=[{"key": "k1", "value": "v1"}],
    )
    request_data = {"headers": {}}
    await builder._process_request_body(request_data, iface)
    assert "data" in request_data
    assert request_data["headers"].get("Content-Type") == "application/x-www-form-urlencoded"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_process_request_body_data_with_text_items(builder):
    """body_type=Data + 文本项: 写入 'data', Content-Type 由 httpx 自定 (None)。"""
    iface = _build_interface(
        body_type=InterfaceRequestTBodyTypeEnum.Data,
        data=[{"key": "k1", "value": "v1", "value_type": "text"}],
    )
    request_data = {"headers": {}}
    await builder._process_request_body(request_data, iface)
    assert "data" in request_data
    assert request_data["data"] == {"k1": "v1"}


# --------------------------------------------------------------------------- #
# _prepare_auth (staticmethod, 不依赖 self)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_prepare_auth_no_auth_does_nothing():
    """auth_type=No_Auth: 不加任何 auth header。"""
    iface = _build_interface(auth_type=InterfaceAuthType.No_Auth)
    request_data = {"headers": {}}
    await RequestBuilder._prepare_auth(request_data, iface)
    assert request_data == {"headers": {}}


@pytest.mark.asyncio
@pytest.mark.unit
async def test_prepare_auth_basic_adds_authorization_header():
    """auth_type=BASIC_Auth: 加 Authorization: Basic <base64>。"""
    iface = _build_interface(
        auth_type=InterfaceAuthType.BASIC_Auth,
        auth={"username": "u", "password": "p"},
    )
    request_data = {"headers": {}}
    await RequestBuilder._prepare_auth(request_data, iface)
    assert "Authorization" in request_data["headers"]
    # base64("u:p") = "dTpw"
    assert request_data["headers"]["Authorization"].startswith("Basic ")
    import base64
    encoded = request_data["headers"]["Authorization"].split(" ", 1)[1]
    assert base64.b64decode(encoded).decode() == "u:p"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_prepare_auth_bearer_adds_authorization_header():
    """auth_type=BEARER_Auth: 加 Authorization: Bearer xxx。"""
    iface = _build_interface(
        auth_type=InterfaceAuthType.BEARER_Auth,
        auth={"token": "abc123"},
    )
    request_data = {"headers": {}}
    await RequestBuilder._prepare_auth(request_data, iface)
    assert request_data["headers"]["Authorization"] == "Bearer abc123"


# --------------------------------------------------------------------------- #
# _filter_request_body
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.unit
async def test_filter_request_body_removes_empty(builder):
    """空 value / None 应被过滤。"""
    data = [
        {"key": "k1", "value": "v1"},
        {"key": "k2", "value": ""},
        {"key": "k3", "value": None},
        {"key": "k4", "value": "v4"},
    ]
    iface = _build_interface(body_type=InterfaceRequestTBodyTypeEnum.UrlEncoded, data=data)
    body_dict, body_str = await builder._filter_request_body(iface)
    # UrlEncoded 返回 {"data": {k1: v1, k4: v4}}, 因为走 _prepare_form_urlencoded
    assert "data" in body_dict
    inner = body_dict["data"]
    assert "k1" in inner
    assert "k4" in inner
    assert "k2" not in inner
    assert "k3" not in inner


@pytest.mark.asyncio
@pytest.mark.unit
async def test_filter_request_body_raw_text(builder):
    """body_type=Raw + raw_type=text: 走 _prepare_raw_body。"""
    iface = _build_interface(
        body_type=InterfaceRequestTBodyTypeEnum.Raw,
        raw_type="text",
        body="hello world",
    )
    body_dict, content_type = await builder._filter_request_body(iface)
    assert body_dict.get("content") == "hello world"
    assert content_type == "text/plain"
