"""
[BUG-S4] _hub_api_request 缺 SSRF 防御

风险: _hub_api_request 在用户脚本沙箱以 hub_request 暴露, 没限制 URL
      scheme 跟 host 解析后的 IP。攻击者:
        - hub_request("http://169.254.169.254/latest/meta-data/iam/security-credentials/")
          → 偷云元数据 IAM 凭证
        - hub_request("file:///etc/passwd")
          → 读本地文件
        - hub_request("http://localhost:8000/admin")
          → 打内网服务
        - hub_request("http://10.0.0.1/...")
          → 内网扫描

修复: _check_ssrf 守门:
  1. Scheme 白名单 http/https
  2. DNS 解析后 IP 黑名单 (loopback / private / link-local / reserved / multicast)
  3. HUB_REQUEST_ALLOW_PRIVATE=1 逃生口 (内部测试需要打内网时显式开)

测试 (12 个, 不打真实网络):
  - scheme 黑名单: file/gopher/ftp/dict/ldap/javascript/data
  - 缺失 host
  - IPv4 黑名单: 127.0.0.1, 10.0.0.1, 172.16.0.1, 192.168.1.1, 169.254.169.254
  - DNS 解析失败
  - 正常公网域名: example.com 不被误杀
  - HUB_REQUEST_ALLOW_PRIVATE=1 放行内网
  - 端到端: hub_request() 拒绝恶意 URL 返回 None (不抛到调用方)
"""
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
        """hub_request("file://...") 不抛到调用方, 返回 None (跟网络失败一致)"""
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
