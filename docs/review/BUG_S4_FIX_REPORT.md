# BUG-S4 Fix Report: `hub_request` 缺 SSRF 防御

**触发版本**: master (S4 之前)
**风险面**: 高 — 用户脚本沙箱内可访问任意内网/云元数据/本地文件
**Commit**: (本 fix)
**测试**: `tests/croe/a_manager/test_bug_s4_hub_request_ssrf.py` (23 个)

---

## 现象 (理论攻击向量)

`_hub_api_request` 在 ScriptManager 的 `_allowed_functions` 里以 `hub_request` 名义暴露给用户脚本沙箱。原代码:

```python
async with httpx.AsyncClient(timeout=10) as client:
    response = await client.request(method=method, url=url, **kwargs)
```

`url` 来自用户脚本内容,完全不受信任。攻击者写测试脚本时可:

| 攻击 | URL 例子 | 后果 |
|---|---|---|
| 偷云元数据 IAM 凭证 | `http://169.254.169.254/latest/meta-data/iam/security-credentials/` | 在 AWS EC2 部署时直接拿角色凭证 |
| 读本地文件 | `file:///etc/passwd`, `file:///proc/self/environ` | 泄露系统配置 / 环境变量(含数据库密码) |
| 打内网服务 | `http://localhost:8000/admin`, `http://10.0.0.1/internal-api` | 越权访问内网管理接口 |
| 端口扫描 | `gopher://`, `dict://internal:11211/stat` (memcached) | redis/memcached/elasticsearch 未授权访问 |
| 协议走私 | `javascript:`, `data:text/html,...` | 反射型 XSS 在前端 hub_request 响应展示时 |

---

## 修复

新增两个模块级函数 (`croe/a_manager/script_manager.py`):

### 1. `_check_ssrf(url)` — 守门

```python
def _check_ssrf(url: str) -> None:
    """SSRF 防御: scheme 白名单 + DNS 解析后 IP 黑名单。"""
    parsed = urlparse(url)

    # 1. Scheme 白名单 — 不允许 file/gopher/ftp/dict/ldap/javascript/data 等
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"hub_request 不允许 scheme '{parsed.scheme}' (仅 http/https)")

    # 2. 必须有 host
    if not parsed.hostname:
        raise ValueError(f"hub_request URL 缺少 host: {url!r}")

    # 3. DNS 解析 + 任何一个解析 IP 命中黑名单就拒
    for family, _, _, _, sockaddr in socket.getaddrinfo(parsed.hostname, ...):
        ip = ipaddress.ip_address(sockaddr[0])
        if _is_blocked_ip(ip):
            if os.environ.get("HUB_REQUEST_ALLOW_PRIVATE") != "1":
                raise ValueError(f"hub_request 拒绝访问内网/loopback/link-local IP: {ip}")
            log.warning(f"...放行...")
```

### 2. `_is_blocked_ip(ip)` — IP 黑名单

```python
def _is_blocked_ip(ip) -> bool:
    """覆盖 127/8, 10/8, 172.16/12, 192.168/16, 169.254/16 (含云元数据),
    IPv6 ::1, fc00::/7, fe80::/10, 0.0.0.0, multicast, reserved"""
```

### 3. `_hub_api_request` 入口调用

```python
try:
    _check_ssrf(url)
except ValueError as e:
    log.warning(f"[BUG-S4] hub_request SSRF 拦截: {e}")
    return None
```

- ValueError 走外层 try/except 兜底返回 None, **跟网络失败行为不可区分** (防 SSRF 行为差分泄露)
- `HUB_REQUEST_ALLOW_PRIVATE=1` 逃生口, 内部测试场景需要打内网时显式开 (但 scheme 限制仍生效)

---

## 修复前后对照

| 调用 | 修复前 | 修复后 |
|---|---|---|
| `hub_request("http://169.254.169.254/...")` | 直接发请求, AWS 部署拿 IAM 凭证 | 拒, 返 None, log WARNING |
| `hub_request("file:///etc/passwd")` | httpx 报错, 返 None | 入口直接拒 (scheme 不对) |
| `hub_request("http://localhost/admin")` | 直接打内网 | DNS 解析 → ::1/127.0.0.1, 拒 |
| `hub_request("http://10.0.0.1/internal")` | 直接打内网 | IP 命中 10/8 private, 拒 |
| `hub_request("http://example.com/api")` | 正常 | 正常 |
| `hub_request("http://internal:8000/api")` (HUB_REQUEST_ALLOW_PRIVATE=1) | 正常 | 正常 (WARNING log) |

---

## 关键设计取舍

1. **拒 vs 抛**: 用 ValueError 抛, 外面 try/except 兜成 None, 让"被 SSRF 拦"跟"网络挂了"在调用方**不可区分**, 防行为差分泄露拦截逻辑
2. **scheme 限制无逃生口**: HUB_REQUEST_ALLOW_PRIVATE 只能开 IP 限制, scheme 仍强约束 (file:// 这种永远不该开)
3. **DNS 解析 + getaddrinfo**: 用 getaddrinfo (而非 gethostbyname) 同时拿到 IPv4 + IPv6 解析结果, **任一命中就拒** (防 IPv4-only 黑名单被 IPv6 绕过)
4. **逃生口 vs 默认安全**: 默认严格, 显式开才放, 跟"secure by default"原则对齐

---

## 回归测试 (23 个, 不打真实网络)

`tests/croe/a_manager/test_bug_s4_hub_request_ssrf.py`:

- **TestIsBlockedIp (9 个)**: IPv4 loopback/private/link-local/unspecified + IPv6 loopback/private/link-local + 公网 IP 不被误杀
- **TestCheckSsrf (10 个)**: 6 种危险 scheme (file/gopher/ftp/dict/javascript/data) + 缺失 host + localhost 拒 + ALLOW_PRIVATE 放 + DNS 失败
- **TestHubApiRequestEndToEnd (3 个)**: hub_request() 端到端, 验证 file:// / localhost / 169.254 都被拒且不抛到调用方

**附带**: V4 旧测试加 `_check_ssrf` mock (因为 S4 在 V4 基础上加了入口守门, V4 测试不应真实跑 DNS)

**全量回归**: 146 unit passed (123 老 + 23 新), 0 fail.

---

## 教训

- **"沙箱暴露面"清单化**: ScriptManager 的 `_allowed_functions` 暴露的每个函数都应该审计一遍, 看输入是否完全受信任。本例 `hub_request` 的 url 来自用户脚本, **跟普通 API 一样不可信**
- **DNS rebinding 不在本 PR 范围**: 防御仅看请求前的解析结果, 不阻止 DNS rebinding 攻击 (攻击者用短 TTL 域名, 解析时返回公网 IP, 实际请求时返回内网 IP)。完整防御需要 socks proxy 或 hook socket.connect, 工程量大, 本 PR 不做 (但留逃生口文档化)
- **URL 编码绕过**: `http://127.0.0.1` / `http://[::1]` / `http://2130706433/` (127.0.0.1 的十进制) 等同义写法都走 urlparse + getaddrinfo 解析, 全部命中黑名单, 无需额外处理
