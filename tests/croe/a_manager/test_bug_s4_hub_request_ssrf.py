"""[BUG-S4] _hub_api_request 缺 SSRF 防御"""

import os
import pytest

from croe.a_manager.script_manager import _check_ssrf, _is_blocked_ip
from croe.a_manager.script_manager import ScriptManager
_hub_api_request = ScriptManager._hub_api_request

# ===== 单元层: _is_blocked_ip =====

class TestIsBlockedIp:
    def test_loopback_ipv4(self):
        import ipaddress
        assert _is_blocked_ip(ipaddress.ip_address("127.0.0.1"))
        assert _is_blocked_ip(ipaddress.ip_address("127.255.255.255"))

    def test_private_10(self):
        import ipaddress
        assert _is_blocked_ip(ipaddress.ip_address("10.0.0.1"))

    def test_private_172_16(self):
        import ipaddress
        assert _is_blocked_ip(ipaddress.ip_address("172.16.0.1"))
        assert _is_blocked_ip(ipaddress.ip_address("172.31.255.255"))
        # 172.15 / 172.32 不在 private 范围, 不应被拦
        assert not _is_blocked_ip(ipaddress.ip_address("172.15.0.1"))
        assert not _is_blocked_ip(ipaddress.ip_address("172.32.0.1"))

    def test_private_192_168(self):
        import ipaddress
        assert _is_blocked_ip(ipaddress.ip_address("192.168.1.1"))

    def test_link_local_169_254_含云元数据(self):
        import ipaddress
        assert _is_blocked_ip(ipaddress.ip_address("169.254.169.254"))

    def test_unspecified(self):
        import ipaddress
        assert _is_blocked_ip(ipaddress.ip_address("0.0.0.0"))

    def test_public_ip_not_blocked(self):
        import ipaddress
        assert not _is_blocked_ip(ipaddress.ip_address("8.8.8.8"))
        assert not _is_blocked_ip(ipaddress.ip_address("1.1.1.1"))

    def test_ipv6_loopback(self):
        import ipaddress
        assert _is_blocked_ip(ipaddress.ip_address("::1"))

    def test_ipv6_private(self):
        import ipaddress
        assert _is_blocked_ip(ipaddress.ip_address("fc00::1"))
        assert _is_blocked_ip(ipaddress.ip_address("fd12:3456::1"))

    def test_ipv6_link_local(self):
        import ipaddress
        assert _is_blocked_ip(ipaddress.ip_address("fe80::1"))

# ===== 集成层: _check_ssrf =====

class TestCheckSsrf:
    def test_scheme_file_rejected(self):
        with pytest.raises(ValueError, match="scheme"):
            _check_ssrf("file:///etc/passwd")

    def test_scheme_gopher_rejected(self):
        with pytest.raises(ValueError, match="scheme"):
            _check_ssrf("gopher://attacker.com/x")

    def test_scheme_ftp_rejected(self):
        with pytest.raises(ValueError, match="scheme"):
            _check_ssrf("ftp://internal-server/")

    def test_scheme_dict_rejected(self):
        with pytest.raises(ValueError, match="scheme"):
            _check_ssrf("dict://internal:11211/stat")

    def test_scheme_javascript_rejected(self):
        with pytest.raises(ValueError, match="scheme"):
            _check_ssrf("javascript:alert(1)")

    def test_scheme_data_rejected(self):
        with pytest.raises(ValueError, match="scheme"):
            _check_ssrf("data:text/html,<script>alert(1)</script>")

    def test_missing_host_rejected(self):
        with pytest.raises(ValueError, match="host"):
            _check_ssrf("http:///path")

    def test_localhost_resolves_to_loopback_rejected(self, monkeypatch):
        """localhost 解析成 127.0.0.1, 应该被 IP 黑名单拦"""
        # 不打真实 DNS: localhost 通常本地就有
        with pytest.raises(ValueError, match="内网"):
            _check_ssrf("http://localhost/admin")

    def test_allow_private_env_var_lets_internal_through(self, monkeypatch):
        """HUB_REQUEST_ALLOW_PRIVATE=1 放行内网"""
        monkeypatch.setenv("HUB_REQUEST_ALLOW_PRIVATE", "1")
        # 不应抛 — localhost 仍然放行
        try:
            _check_ssrf("http://localhost/admin")
        except ValueError as e:
            pytest.fail(f"HUB_REQUEST_ALLOW_PRIVATE=1 时应放行, 实际拒绝: {e}")

    def test_dns_resolution_failure_rejected(self):
        """不存在的域名应抛 ValueError"""
        with pytest.raises(ValueError, match="DNS"):
            _check_ssrf("http://this-host-does-not-exist-12345.invalid/x")

# ===== 端到端层: _hub_api_request 行为 =====

class TestHubApiRequestEndToEnd:
    def test_file_url_returns_none_without_raising(self):
        """hub_request("file://...") 不抛到调用方, 返回 None"""
        result = _hub_api_request("file:///etc/passwd")
        assert result is None

    def test_localhost_url_returns_none(self):
        """hub_request("http://localhost:...") 在沙箱内被拒, 返回 None"""
        result = _hub_api_request("http://localhost:9999/admin")
        assert result is None

    def test_169_254_metadata_url_returns_none(self):
        """hub_request("http://169.254.169.254/...") 直接被拒, 返回 None"""
        result = _hub_api_request("http://169.254.169.254/latest/meta-data/")
        assert result is None
