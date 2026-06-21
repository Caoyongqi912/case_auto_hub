# Round 1 安全审计修复报告 (BUG-SEC-2 / BUG-SEC-3 / BUG-SEC-4)

**Commit**: `25bff89 fix(SEC-2/3/4): Round 1 安全审计 3 个 P0 修复 + 单测`
**基线**: 996 → 1005 passed, 0 failed, 1 xfailed
**关联报告**: `docs/review/BUG_SEC_1_AUDIT_REPORT.md` (上一轮)

---

## 风险摘要

| ID | 等级 | 位置 | 风险 |
|---|---|---|---|
| BUG-SEC-2 | **P0** | `croe/interface/builder/url_builder.py` | SSRF: 用户可借本服务请求内网 / 云元数据 (169.254.169.254) / loopback |
| BUG-SEC-3 | **P0** | `app/controller/user/user.py::register_admin` | 越权: 任何已登录用户都能注册 admin 账号 |
| BUG-SEC-4 | **P0** | `app/controller/project/db_config.py::get_db` | 明文 db_password 通过 API 返回, 凭据泄露 |

---

## BUG-SEC-2: SSRF 防护

### 根因
`UrlBuilder.build()` 直接拼接 `env.url` + `interface.interface_url`,不做任何 host 校验。攻击者:
- 把 EnvModel.host 改成 `127.0.0.1` → 探测内网存活服务
- 改成 `169.254.169.254` → 读云元数据 IAM 凭据
- 改成 `10.x.x.x` → 横向移动到内网应用

### 修法
新增 `url_builder.py` 模块级函数 (import 时加载, 不增加热路径开销):

```
_allow_private()                  - 读 env SSRF_ALLOW_PRIVATE_HOSTS, 默认关闭
_is_private(ip)                   - 综合 is_private / is_loopback / is_link_local / is_reserved / is_multicast / is_unspecified
_strip_port(host)                 - 容忍 host:port / [::1]:port / ::1:port 等多种形式
_resolve_host_is_private(host)    - IP 字面量走 ipaddress, 域名走 thread+3s 超时 getaddrinfo
_extract_host(url_or_host)        - 从 url 或裸 host 提取 host, 支持 IPv6 字面量
_assert_safe_url(url_or_host)     - 串联上述, 命中保留网段抛 ValueError
```

`UrlBuilder.build()` 在两处都调 `_assert_safe_url`:
- custom env (`env_id=99999`): `interface.interface_url` 整段
- 普通 env: `f"{base_url}/{path}"` 拼接后

### 部署注意
- 默认: 拒绝内网
- 内网测试: 设 `SSRF_ALLOW_PRIVATE_HOSTS=1` 显式放开
- IPv6 防护已覆盖 (`::1`, `fe80::/10`, `2001:db8::/32` 等)
- 域名解析超时 3s, 不会让恶意 slow-resolve 域名永久阻塞请求

---

## BUG-SEC-3: registerAdmin 鉴权

### 根因
`POST /user/registerAdmin` 原签名:
```python
async def register_admin(user: RegisterSchema):
    ...
```
没有 `Depends(Authentication(...))`,任何调用方都可以创建 admin 账号。

### 修法
```python
async def register_admin(
    user: RegisterSchema,
    admin: User = Depends(Authentication(isAdmin=True)),
):
    ...
```

这样未登录访问直接 401, 普通用户访问 403, 只有 admin 能调用。

### 部署注意
- 首次启动若没有 admin: 需要从 DB 直接 INSERT 或临时关掉这个鉴权 (不推荐, 应留 1 个引导账号)

---

## BUG-SEC-4: get_db 遮蔽 password

### 根因
`GET /project/config/infoDB?uid=...` 直接返回 `DbConfig` ORM 对象,`db_password` 字段明文出现在 JSON response 里。

`pageDB` / `queryDB` 已经用 `Response.success(db, exclude=DB_Exclude)`,但 `get_db` 漏了。

### 修法
`get_db` 改用 `Response.success(db, exclude=DB_Exclude)`。
`DB_Exclude = {"db_username", "db_password", "db_port", "db_host"}` 已在模块顶部定义。

### 后续
- 如果前端某些场景确实需要明文密码 (例如单次测试连接), 应走专门的解密接口 (POST + 二次鉴权 + 审计日志), 当前不返回明文。
- 已有密码建议轮换 (因为已经暴露过, 假设是内网白盒环境)。

---

## 测试覆盖

`tests/security/test_round1_security_fixes.py` 新增 9 个用例:

| 用例 | 锁定行为 |
|---|---|
| `test_url_builder_blocks_loopback_ipv4` | `127.0.0.1:8000` 必须 raise |
| `test_url_builder_blocks_loopback_ipv6` | `::1:8000` 必须 raise (IPv6) |
| `test_url_builder_blocks_metadata_service` | `169.254.169.254` 必须 raise |
| `test_url_builder_blocks_rfc1918` | `10.0.0.5:8080` 必须 raise |
| `test_url_builder_blocks_custom_env_private` | `env_id=99999` 的 `http://127.0.0.1:6006/mini` 必须 raise |
| `test_url_builder_allows_public_ip` | `8.8.8.8:443/api` 必须放行 |
| `test_url_builder_allow_private_bypass` | `SSRF_ALLOW_PRIVATE_HOSTS=1` 时内网放行 |
| `test_register_admin_route_has_admin_auth` | register_admin 签名必须含 `Authentication(isAdmin=True)` |
| `test_get_db_route_masks_password` | get_db 内 `Response.success` 必须带 `DB_Exclude` |

---

## 下一轮

进入 **Round 2: 资源泄漏审计** (DB session / Redis / 文件句柄 / httpx)。
