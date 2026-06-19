"""
url_builder.py 单测覆盖率补充 (目标 44% → 80%+)。

测 UrlBuilder.build 的 3 条主路径:
1. env_id == CUSTOM_ENV_ID (99999): 走自定义 URL
2. env=None: raise ValueError
3. 正常路径: base_url + '/' + path, 去尾斜杠
"""
import pytest

from croe.interface.builder.url_builder import UrlBuilder


def _build_interface(env_id=1, interface_url="/api/v1/users"):
    iface = MagicMock()
    iface.id = 100
    iface.env_id = env_id
    iface.interface_url = interface_url
    return iface


def _build_env(env_url="http://example.com"):
    env = MagicMock()
    env.url = env_url
    return env


# 用 unittest.mock.MagicMock 不直接 from, 避免循环
from unittest.mock import MagicMock


@pytest.mark.asyncio
@pytest.mark.unit
async def test_url_builder_custom_env_uses_interface_url_directly():
    """env_id=CUSTOM_ENV_ID: 直接用 interface.interface_url, 不拼 env。"""
    iface = _build_interface(env_id=UrlBuilder.CUSTOM_ENV_ID, interface_url="https://custom.example.com/special")
    env = _build_env(env_url="http://should-be-ignored.com")
    url = await UrlBuilder.build(iface, env)
    assert url == "https://custom.example.com/special"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_url_builder_no_env_raises_value_error():
    """env=None 且 env_id != CUSTOM_ENV_ID: raise ValueError。"""
    iface = _build_interface(env_id=1, interface_url="/api/v1/users")
    with pytest.raises(ValueError, match="未提供环境配置"):
        await UrlBuilder.build(iface, env=None)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_url_builder_normal_path_strips_trailing_slash():
    """正常路径: base_url 去尾斜杠, path 去头斜杠, 用 '/' 拼。"""
    iface = _build_interface(env_id=1, interface_url="/api/v1/users")
    env = _build_env(env_url="http://example.com/")
    url = await UrlBuilder.build(iface, env)
    assert url == "http://example.com/api/v1/users"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_url_builder_path_no_leading_slash_still_works():
    """path 没有前导 / 也 OK, 强制加 '/'。"""
    iface = _build_interface(env_id=1, interface_url="api/v1/users")
    env = _build_env(env_url="http://example.com")
    url = await UrlBuilder.build(iface, env)
    assert url == "http://example.com/api/v1/users"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_url_builder_base_no_trailing_slash_normal():
    """base_url 没有尾斜杠: 仍能正常拼。"""
    iface = _build_interface(env_id=1, interface_url="/path")
    env = _build_env(env_url="http://example.com")
    url = await UrlBuilder.build(iface, env)
    assert url == "http://example.com/path"
