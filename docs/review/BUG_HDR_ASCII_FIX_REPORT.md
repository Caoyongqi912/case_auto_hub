# BUG-HDR-ASCII 修复报告

**发现时间**: 2026-06-20
**影响**: 接口请求失败
**优先级**: P1 (业务挂)

## 现象

接口请求 `/mini/randomName` 报:

```
'ascii' codec can't encode characters in position 1-8: ordinal not in range(128)
```

调用栈:
```
File "croe/interface/executor/interface_executor.py", line 154, in _build_and_send_request
    ctx.response = await self.http(method=ctx.interface.interface_method, **ctx.request_info)
File "common/httpxClient.py", line 117, in _request
    response = await self.client.request(method, url, **kwargs)
File ".venv/lib/python3.13/site-packages/httpx/_models.py", line 82, in _normalize_header_value
    return value.encode(encoding or "ascii")
UnicodeEncodeError
```

## 根因

HTTP/1.1 spec (RFC 7230) 规定 header value 必须是 ASCII。`httpx._models._normalize_header_value` 默认按 `ascii` 编码, 用户在 `g_headers` (InterfaceGlobalHeader) 或 `interface_headers` 里配中文 / emoji / 重音字符等非 ASCII 值时, 整请求挂。

错误信息指向 httpx 内部, 用户看不出是 header 配错。

## 修复

**文件**: `croe/interface/builder/request_builder.py:_prepare_headers`

```python
# BUG-HDR-ASCII 修复: HTTP/1.1 header value 必须是 ASCII (RFC 7230),
# httpx 默认按 ascii 编码, 用户在 g_headers / interface_headers 里
# 配中文 / emoji / 重音字符等非 ASCII 值时会抛 UnicodeEncodeError。
# 修: 在这里做一遍校验, 非 ASCII 值用 UTF-8 percent-encode, ...
for k, v in list(headers.items()):
    if not isinstance(v, str) or v.isascii():
        continue
    encoded = urllib.parse.quote(v, safe="")
    log.warning(
        f"[BUG-HDR-ASCII] header 值含非 ASCII 字符, 自动 percent-encode: "
        f"{k!r}={v!r} -> {encoded!r} (case_id={case_id})..."
    )
    headers[k] = encoded
```

**行为**:
1. ASCII header value: 不动
2. 非 ASCII (中文 / emoji / 重音 / mixed): 自动 UTF-8 percent-encode
3. WARNING log 留痕, 告诉用户是哪个 header 触发的
4. server 端用 `urllib.parse.unquote` 解码即可拿到原文

**对比方案**:

| 方案 | 行为 | 评价 |
|---|---|---|
| A. 当前选: 自动 percent-encode + WARNING | 业务不挂, 用户能看到日志 | ✅ 选 |
| B. 不修, 让 httpx 抛 UnicodeEncodeError | 业务挂, 错误信息指向 httpx 内部, 用户看不出 header 配错 | ❌ |
| C. 静默跳过非 ASCII header | 用户不知情, 接口莫名少 header | ❌ |
| D. 全局替换 httpx encoding 为 utf-8 | 改 client 全局行为, 影响范围太大; HTTP/1.1 spec 仍是 ASCII, server 不一定认 utf-8 | ❌ |

## 验证

**回归测试** (14 测, 全部新增):
- `tests/croe/interface/test_bug_hdr_ascii_non_ascii_header_value.py`

测试覆盖:
- ASCII 值不动 (3 测: plain / token / empty)
- 中文 / emoji / 重音 / mixed 字符自动 percent-encode (5 测)
- 业务不挂 (2 测: 中文/emoji 值不再抛 UnicodeEncodeError)
- g_headers 处理 (1 测)
- 边界 (3 测: unicode 4-byte / 非 ASCII 在中间 / 复现错误位置 1-8)

**全量回归**:
```
685 passed, 2 skipped, 3 deselected, 1 xfailed, 6 warnings in 77.74s
```

**基线 414 → 685 (+271, 0 fail)**

## commit

`ef60f46` fix(BUG-HDR-ASCII): 非 ASCII header value 自动 percent-encode
