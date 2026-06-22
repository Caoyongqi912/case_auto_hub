"""Round 1 安全审计修复.

锁定行为:
- SSRF 防护 (url_builder._assert_safe_url)
- registerAdmin 必须 admin 鉴权
- get_db 端点必须 mask password
"""
import re
from pathlib import Path
from unittest.mock import patch

import pytest


# --------------------------------------------------------------------------- #
# SSRF 防护
# --------------------------------------------------------------------------- #
class _FakeEnvModel:
    """最小化 EnvModel 替身, 只让 url_builder 用 url 属性。"""
    def __init__(self, host: str, port: str = ""):
        self.host = host
        self.port = port or None

    @property
    def url(self) -> str:
        domain = self.host
        if self.port:
            domain += f":{self.port}"
        return domain


class _FakeInterface:
    def __init__(self, env_id: int, url: str = ""):
        self.env_id = env_id
        self.interface_url = url


@pytest.mark.unit
@pytest.mark.asyncio
async def test_url_builder_blocks_loopback_ipv4(monkeypatch):
    """UrlBuilder.build 必须拒绝 127.0.0.1 (loopback)."""
    from croe.interface.builder.url_builder import UrlBuilder
    iface = _FakeInterface(env_id=1, url="/api/x")
    env = _FakeEnvModel(host="127.0.0.1", port="8000")
    # 关掉 _ALLOW_PRIVATE 开关
    monkeypatch.setenv("SSRF_ALLOW_PRIVATE_HOSTS", "0")
    with pytest.raises(ValueError, match="SSRF"):
        await UrlBuilder.build(interface=iface, env=env)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_url_builder_blocks_metadata_service(monkeypatch):
    """UrlBuilder.build 必须拒绝 169.254.169.254 (云元数据)."""
    from croe.interface.builder.url_builder import UrlBuilder
    iface = _FakeInterface(env_id=1, url="/latest/meta-data/")
    env = _FakeEnvModel(host="169.254.169.254")
    monkeypatch.setenv("SSRF_ALLOW_PRIVATE_HOSTS", "0")
    with pytest.raises(ValueError, match="SSRF"):
        await UrlBuilder.build(interface=iface, env=env)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_url_builder_blocks_rfc1918(monkeypatch):
    """UrlBuilder.build 必须拒绝 10.0.0.0/8 (RFC1918 私网)."""
    from croe.interface.builder.url_builder import UrlBuilder
    iface = _FakeInterface(env_id=1, url="/internal")
    env = _FakeEnvModel(host="10.0.0.5", port="8080")
    monkeypatch.setenv("SSRF_ALLOW_PRIVATE_HOSTS", "0")
    with pytest.raises(ValueError, match="SSRF"):
        await UrlBuilder.build(interface=iface, env=env)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_url_builder_blocks_loopback_ipv6(monkeypatch):
    """UrlBuilder.build 必须拒绝 [::1] (IPv6 loopback)."""
    from croe.interface.builder.url_builder import UrlBuilder
    iface = _FakeInterface(env_id=1, url="/api")
    env = _FakeEnvModel(host="::1", port="8000")
    monkeypatch.setenv("SSRF_ALLOW_PRIVATE_HOSTS", "0")
    with pytest.raises(ValueError, match="SSRF"):
        await UrlBuilder.build(interface=iface, env=env)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_url_builder_blocks_custom_env_private(monkeypatch):
    """custom env (env_id=99999) 的 interface_url 也必须走 SSRF 校验."""
    from croe.interface.builder.url_builder import UrlBuilder
    iface = _FakeInterface(env_id=UrlBuilder.CUSTOM_ENV_ID, url="http://127.0.0.1:6006/mini")
    monkeypatch.setenv("SSRF_ALLOW_PRIVATE_HOSTS", "0")
    with pytest.raises(ValueError, match="SSRF"):
        await UrlBuilder.build(interface=iface)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_url_builder_allows_public_ip(monkeypatch):
    """公网 IP 字面量 (8.8.8.8) 必须放行."""
    from croe.interface.builder.url_builder import UrlBuilder
    monkeypatch.setenv("SSRF_ALLOW_PRIVATE_HOSTS", "0")
    iface = _FakeInterface(env_id=1, url="/api/v1")
    env = _FakeEnvModel(host="8.8.8.8", port="443")
    url = await UrlBuilder.build(interface=iface, env=env)
    assert url == "8.8.8.8:443/api/v1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_url_builder_allow_private_bypass(monkeypatch):
    """_ALLOW_PRIVATE=True 时内网也放行 (内网测试场景)."""
    from croe.interface.builder.url_builder import UrlBuilder
    monkeypatch.setenv("SSRF_ALLOW_PRIVATE_HOSTS", "1")
    iface = _FakeInterface(env_id=1, url="/api")
    env = _FakeEnvModel(host="127.0.0.1", port="8000")
    url = await UrlBuilder.build(interface=iface, env=env)
    assert url == "127.0.0.1:8000/api"


# --------------------------------------------------------------------------- #
# registerAdmin 必须 admin 鉴权
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_register_admin_route_has_admin_auth():
    """POST /user/registerAdmin 必须挂 admin 鉴权, 否则任何人都能注册 admin."""
    src = Path("app/controller/user/user.py").read_text()
    m = re.search(
        r'async def register_admin\(([^)]+)\)',
        src,
        re.DOTALL,
    )
    assert m, "找不到 register_admin 路由"
    sig = m.group(1)
    assert "Authentication" in sig, (
        f"register_admin 必须有 Authentication 依赖, 当前签名: {sig!r}"
    )
    assert "isAdmin=True" in sig, (
        f"register_admin 必须 isAdmin=True (普通用户无权创建 admin), 当前签名: {sig!r}"
    )


# --------------------------------------------------------------------------- #
# get_db 端点必须 mask password
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_get_db_route_masks_password():
    """GET /project/config/infoDB 必须用 DB_Exclude 遮蔽 db_password."""
    src = Path("app/controller/project/db_config.py").read_text()
    # 定位 get_db 函数体起点
    m = re.search(r'async def get_db\b', src)
    assert m, "找不到 get_db 函数"
    rest = src[m.end():]
    # 函数体到下一个 @router 装饰器 / async def / def / class 为止
    end_match = re.search(r'\n(@router|async def |def |class )', rest)
    assert end_match, "找不到 get_db 函数体结尾"
    body = rest[:end_match.start()]
    # 函数体里必须有 Response.success 调用, 且参数里带 DB_Exclude
    success_calls = re.findall(r'Response\.success\(([^)]*)\)', body)
    assert success_calls, "get_db 内没有 Response.success 调用"
    masked = any("DB_Exclude" in call for call in success_calls)
    assert masked, (
        f"get_db 必须用 DB_Exclude 遮蔽 db_password, "
        f"实际 Response.success 调用: {success_calls!r}"
    )

