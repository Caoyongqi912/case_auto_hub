"""非 ASCII header value 自动 percent-encode 行为测试。"""
import pytest
from unittest.mock import MagicMock

from croe.interface.builder.request_builder import RequestBuilder


def _make_interface(headers_json=None):
    """构造一个 duck-typed Interface (避开 SQLAlchemy 表)。"""
    iface = MagicMock()
    iface.interface_headers = headers_json
    iface.interface_case_id = 1
    iface.interface_method = "GET"
    return iface


def _make_builder():
    """构造一个 RequestBuilder, 不传 g_headers。"""
    from croe.a_manager.variable_manager import VariableManager
    return RequestBuilder(variables=VariableManager(), global_headers=[])


class TestPureAsciiHeaderValues:
    """纯 ASCII header value 不动。"""

    @pytest.mark.asyncio
    async def test_ascii_value_unchanged(self):
        iface = _make_interface(headers_json=[{"key": "X-Custom", "value": "plain-text"}])
        builder = _make_builder()
        headers = await builder._prepare_headers(iface)
        assert headers["X-Custom"] == "plain-text"

    @pytest.mark.asyncio
    async def test_token_value_unchanged(self):
        iface = _make_interface(headers_json=[
            {"key": "Authorization", "value": "Bearer abc123.def456-ghi"}
        ])
        builder = _make_builder()
        headers = await builder._prepare_headers(iface)
        assert headers["Authorization"] == "Bearer abc123.def456-ghi"

    @pytest.mark.asyncio
    async def test_whitespace_only_value_is_filtered(self):
        """业务约定: list2dict 过滤纯空白 value (key 留, value 空)。"""
        iface = _make_interface(headers_json=[{"key": "X-WS", "value": "   "}])
        builder = _make_builder()
        headers = await builder._prepare_headers(iface)
        # 纯空白 value 被 list2dict 过滤, headers 里没有这个 key
        assert "X-WS" not in headers


class TestNonAsciiHeaderValues:
    """非 ASCII header value 应自动 percent-encode。"""

    @pytest.mark.asyncio
    async def test_chinese_value_percent_encoded(self):
        """中文值应被 UTF-8 percent-encode: '测试' -> '%E6%B5%8B%E8%AF%95'。"""
        iface = _make_interface(headers_json=[{"key": "X-Custom", "value": "测试"}])
        builder = _make_builder()
        headers = await builder._prepare_headers(iface)
        # urllib.parse.quote("测试", safe="") 默认 UTF-8
        assert headers["X-Custom"] == "%E6%B5%8B%E8%AF%95"

    @pytest.mark.asyncio
    async def test_emoji_value_percent_encoded(self):
        iface = _make_interface(headers_json=[{"key": "X-Emoji", "value": "hi 🚀"}])
        builder = _make_builder()
        headers = await builder._prepare_headers(iface)
        # emoji 🚀 是 U+1F680, UTF-8 编码 0xF0 0x9F 0x9A 0x80
        assert "%F0%9F%9A%80" in headers["X-Emoji"]

    @pytest.mark.asyncio
    async def test_mixed_ascii_and_chinese(self):
        """混合 ASCII + 中文, 整串 percent-encode: 'a测试b' -> 'a%E6%B5%8B%E8%AF%95b'。"""
        iface = _make_interface(headers_json=[{"key": "X-Mix", "value": "a测试b"}])
        builder = _make_builder()
        headers = await builder._prepare_headers(iface)
        assert headers["X-Mix"] == "a%E6%B5%8B%E8%AF%95b"

    @pytest.mark.asyncio
    async def test_accent_characters_percent_encoded(self):
        """重音字符 (Latin-1 之外) 也会被 percent-encode。"""
        iface = _make_interface(headers_json=[{"key": "X-Accent", "value": "café"}])
        builder = _make_builder()
        headers = await builder._prepare_headers(iface)
        # 'é' (U+00E9) -> '%C3%A9' in UTF-8
        assert headers["X-Accent"] == "caf%C3%A9"

    @pytest.mark.asyncio
    async def test_all_chinese_value(self):
        """业务场景: 用户在 g_headers 里配 'X-Region: 国内'。"""
        iface = _make_interface(headers_json=[{"key": "X-Region", "value": "国内"}])
        builder = _make_builder()
        headers = await builder._prepare_headers(iface)
        # '国内' UTF-8 -> %E5%9B%BD%E5%86%85
        assert headers["X-Region"] == "%E5%9B%BD%E5%86%85"


class TestNonAsciiHeaderEdgeCases:
    """边界情况。"""

    @pytest.mark.asyncio
    async def test_unicode_only_emoji(self):
        iface = _make_interface(headers_json=[{"key": "X-Emoji", "value": "🎉"}])
        builder = _make_builder()
        headers = await builder._prepare_headers(iface)
        # 4-byte UTF-8 sequence
        assert "%F0%9F%8E%89" in headers["X-Emoji"]

    @pytest.mark.asyncio
    async def test_non_ascii_in_middle(self):
        """模拟错误中的 'position 1-8': 'a' + 8 chars Chinese + 后续。"""
        iface = _make_interface(headers_json=[{"key": "X-Pos", "value": "a测b试c测d试e"}])
        builder = _make_builder()
        headers = await builder._prepare_headers(iface)
        # 整个 string 都 percent-encode (不只是非 ASCII 部分)
        assert "%" in headers["X-Pos"]
        # 没有原始中文字符
        assert "测" not in headers["X-Pos"]
        assert "试" not in headers["X-Pos"]


class TestNonAsciiHeadersDontCrash:
    """业务不挂: 不应再抛 UnicodeEncodeError。"""

    @pytest.mark.asyncio
    async def test_chinese_value_does_not_raise(self):
        """关键回归: 之前会抛 UnicodeEncodeError, 现在不应抛。"""
        iface = _make_interface(headers_json=[
            {"key": "X-Token", "value": "token测试123"}
        ])
        builder = _make_builder()
        # 不应抛
        headers = await builder._prepare_headers(iface)
        assert "X-Token" in headers
        # 值已 percent-encode
        assert "测" not in headers["X-Token"]

    @pytest.mark.asyncio
    async def test_emoji_value_does_not_raise(self):
        iface = _make_interface(headers_json=[{"key": "X-Emoji", "value": "🎉🎊"}])
        builder = _make_builder()
        headers = await builder._prepare_headers(iface)
        assert "X-Emoji" in headers


class TestGlobalHeaderNonAscii:
    """g_headers (InterfaceGlobalHeader) 里的非 ASCII 值也处理。"""

    @pytest.mark.asyncio
    async def test_global_header_chinese_value_encoded(self):
        from app.model.interfaceAPIModel.interfaceGlobalModel import InterfaceGlobalHeader
        g = MagicMock(spec=InterfaceGlobalHeader)
        g.map = {"X-Global": "测试值"}
        builder = RequestBuilder(
            variables=MagicMock(),
            global_headers=[g],
        )
        iface = _make_interface(headers_json=None)  # 无 interface_headers
        headers = await builder._prepare_headers(iface)
        assert headers["X-Global"] == "%E6%B5%8B%E8%AF%95%E5%80%BC"


class TestHeaderKeyIsAscii:
    """header key 也应是 ASCII (RFC 7230), 但现状是 key 也可能被配成中文。

    实际修复范围限定 value (httpx 报错指向 value.encode), key 不在
    本次修复范围 (key 走 _normalize_header_key, 同样 ascii, 同样会
    抛 UnicodeEncodeError, 但频率极低, 单独 BUG)。
    """

    @pytest.mark.asyncio
    async def test_ascii_key_chinese_value(self):
        """ASCII key + 中文 value: value 应被 percent-encode。"""
        iface = _make_interface(headers_json=[{"key": "X-Token", "value": "测试"}])
        builder = _make_builder()
        headers = await builder._prepare_headers(iface)
        assert "X-Token" in headers
        assert headers["X-Token"] == "%E6%B5%8B%E8%AF%95"
