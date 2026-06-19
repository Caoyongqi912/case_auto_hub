# BUG-E7 + V3 + S5 + S7 + D9 Fix Report: 5 个 easy wins 一锅端

**触发版本**: master
**Commit**: (本 fix)
**测试**: `tests/croe/interface/test_bug_e7_v3_s5_s7_d9_batch.py` (14 个)

---

## 现象 (5 个 BUG, 1h30 内一锅修)

### E7 [中] extracts/asserts 默认值混乱
- 位置: `interface_executor.py:417-418` `'extracts': ctx.extracted_vars or [], 'asserts': ctx.asserts or []`
- `or []` 只挡 `None`, 不挡 `[None]` (子策略可能传 `asserts=[None]` 进来)
- 后果: `[None]` 存到 DB, 后续 JSON 序列化失败 (前端展示炸)
- 修: 显式 list comprehension 过滤 `None` 项

### V3 [中高] ScriptManager._variables 跨脚本累积
- 位置: `script_manager.py:230` `self._variables: Dict[str, Any] = {}` + `_collect_results` 累积
- 当前 `interface_executor` 每次 `ScriptManager()` 新建, **不泄漏**
- 隐患: 语义不明 (累积是"故意"还是"忘清"?), 后来人加缓存 / 复用就立刻踩
- 修: 重命名 `_variables` → `_script_locals`, 注释清楚"单实例跨 exec 是 *故意* 累积, 跨 ScriptManager 实例不共享"

### S5 [中高] _prepare_raw_body raw text 模式多余 json.dumps
- 位置: `request_builder.py:276` `return ({KEY_CONTENT: json.dumps(interface.interface_body)}, "text/plain")`
- raw_type == text 时, body 是 str, 走 json.dumps:
  1. 加多余引号: `"hello"` → `'"hello"'` (错, 实际想发 `hello`)
  2. 反斜杠被 double-escape: `"C:\\path"` → `'"C:\\\\path"'`
  3. 用户已有的 JSON 字符串被 re-encode, 变量替换后意义变
- 修: body 是 str 直接用, 不是 str (dict/list) 才 json.dumps

### S7 [低] safe_headers 不拦截下游 interface_headers
- 位置: `request_builder.py:_prepare_headers` 信任 `g_headers` + `interface_headers`
- 用户可配 `Host: malicious` 改后端真实 host, 配 `Content-Length: 999999` 改 body 大小让后端 parse 错
- 修: 加 `BLOCKED_DOWNSTREAM_HEADERS` 黑名单 (Host / Content-Length / Connection / Transfer-Encoding / Upgrade), 拦截 WARNING 留痕, 不静默

### D9 [中] 2 个 pass 占位方法
- 位置: `interfaceResultMapper.py:39-46` `page_case_results` / `query_case_result` 是空 `pass`
- 没 `NotImplementedError` / TODO 标记, 后续维护者分不清"忘写了" vs "故意占位"
- 修: 改 `raise NotImplementedError` + 详细 TODO 注释 (引导调用方走 `get_by_id`)

---

## 修复 (5 处小改, 0 风险)

### E7: 2 行
```python
# 旧
'extracts': ctx.extracted_vars or [],
'asserts': ctx.asserts or [],
# 新
'extracts': [v for v in (ctx.extracted_vars or []) if v is not None],
'asserts': [a for a in (ctx.asserts or []) if a is not None],
```

### V3: 7 处改名 + 注释
```python
self._script_locals: Dict[str, Any] = {}  # 旧: self._variables
# ... 7 处 self._variables 改 self._script_locals
# docstring 加 BUG-V3 标记
```

### S5: 1 行 (核心)
```python
# 旧
{KEY_CONTENT: json.dumps(interface.interface_body)}
# 新
{KEY_CONTENT: interface.interface_body
 if isinstance(interface.interface_body, str)
 else json.dumps(interface.interface_body)}
```

### S7: 1 常量 + 过滤逻辑
```python
BLOCKED_DOWNSTREAM_HEADERS = frozenset({
    "host", "content-length", "connection", "transfer-encoding", "upgrade",
})
# _prepare_headers 循环里: if k.lower() in BLOCKED, log.warning + skip
```

### D9: 2 个 raise
```python
raise NotImplementedError(
    "page_case_results is a placeholder (BUG-D9), "
    "实现前请先确认是否真的需要此接口, 还是走 list_by_filter + 分页"
)
```

---

## 关键设计取舍

1. **E7 显式 list comprehension 而非 `or []`**: 防御性编程, 防止 [None] 透传
2. **V3 改名 + 注释, 不删累积**: 累积是 *ScriptManager 实例内* 故意行为 (一个脚本多个 exec 阶段共享 var), 跨实例不共享。改名让"故意"vs"应该清"的边界清晰
3. **S5 str 判断**: 跟 JSON 模式 (dict → KEY_JSON) 不冲突, 跟用户意图对齐 (raw text 模式 body 是 str)
4. **S7 黑名单 5 个**: 选最常见的 5 个 (host/content-length/connection/transfer-encoding/upgrade), 多了误伤正常 header, 少了漏覆盖
5. **D9 raise NotImplementedError**: 跟 pass 比, 调用方立刻知道这是占位; 跟删方法比, 不破坏 import 兼容性
6. **5 个 BUG 互不依赖**: 改 5 个不同文件, 串行安全, 各自 commit 也行; 合一个 commit 因为都是 easy wins + 共同 review

---

## 修复前后对照

| 场景 | 修复前 | 修复后 |
|---|---|---|
| 子策略传 `asserts=[None]` | DB 存 `[None]`, 前端展示炸 | 过滤成 `[]`, 安全 ✓ |
| 跨 ScriptManager 实例 var 共享 | 字段名 `_variables` 误导, 复用就泄漏 | `_script_locals` 明确"实例内故意累积, 跨实例不共享" ✓ |
| raw text body = `"hello"` | httpx 发 `'"hello"'` (带 JSON 引号) | httpx 发 `'hello'` ✓ |
| raw text body = `"C:\\path"` | `'"C:\\\\path"'` (反斜杠被 escape) | `"C:\\path"` 原样 ✓ |
| 用户配 `Host: evil.com` | 覆盖后端 host, 请求打错地方 | WARNING 拦截, 用后端真实 host ✓ |
| 用户配 `Content-Length: 999999` | httpx 跟后端 header 打架, 偶发 400 | WARNING 拦截, httpx 算实际 size ✓ |
| 调用 `page_case_results()` | 静默返 `None`, 下游 TypeError 难定位 | `NotImplementedError("BUG-D9 占位")` 立刻知道 ✓ |
| 调用 `query_case_result(42)` | 静默返 `None` | `NotImplementedError` + 提示用 `get_by_id` 替代 ✓ |

---

## 回归测试 (14 个, mock 不接 DB)

`tests/croe/interface/test_bug_e7_v3_s5_s7_d9_batch.py`:

**E7 (1)**:
1. `test_bug_e7_filter_none_in_asserts_and_extracts` — 源码必须显式过滤 None

**V3 (2)**:
2. `test_bug_v3_script_manager_renamed_variables` — `_variables` 全部消失, `_script_locals` 全在
3. `test_bug_v3_hub_variables_methods_use_script_locals` — 3 个 `_hub_variables_*` 方法都用 `_script_locals`

**S5 (4)**:
4. `test_bug_s5_raw_text_with_str_body_not_dumped` — str body 直接用, 不加 JSON 引号
5. `test_bug_s5_raw_text_with_dict_body_still_dumped` — dict body 仍 json.dumps
6. `test_bug_s5_raw_text_str_with_backslashes_not_double_escaped` — 反斜杠不 double-escape
7. `test_bug_s5_json_raw_type_unchanged` — json raw_type 走 KEY_JSON 不变 (回归保护)

**S7 (4)**:
8. `test_bug_s7_blocked_headers_constant_exists` — 5 个必拦 header 在常量里
9. `test_bug_s7_blocks_host_header_in_interface_headers` — Host 拦, 正常 header 透
10. `test_bug_s7_blocks_content_length` — Content-Length 拦
11. `test_bug_s7_normal_headers_still_pass` — Authorization / X-Request-Id 不误拦

**D9 (3)**:
12. `test_bug_d9_page_case_results_raises_not_implemented` — 抛 NotImplementedError
13. `test_bug_d9_query_case_result_raises_not_implemented` — 同上
14. `test_bug_d9_no_plain_pass_in_d9_methods` — 源码里没单独 pass 行

**全量回归**: 243 unit passed (229 老 + 14 新), 0 fail.

---

## 教训

- **easy wins 攒一起做**: 5 个 BUG 各自 5-30 分钟, 单做都"性价比不高", 攒一起 1h30 完事 + 1 个 report + 1 个 commit, ROI 高
- **`or []` 不如显式过滤**: 跟 None 比较, `or` 链只挡 falsy 值, 挡不住 `[None]` / `[0]` 等。**显式 `if x is not None` 比 `or` 安全 10x**
- **跨实例状态易误用**: 字段名 `_variables` 太泛, 后来人不知道是实例级还是模块级。**改名 + 注释**比加 assertion 更有效 (assertion 只防不改语义)
- **str vs dict 在 raw mode 的语义边界**: 用户配 raw text 模式, body 几乎一定是 str。**对 str 走 json.dumps 是反直觉的反模式**, 用户不会期望
- **黑名单 vs 白名单**: S7 选黑名单 (5 个常见敏感 header) 不选白名单, 因为正常 header 太多维护成本高, 敏感 header 数量有限且稳定
- **`pass` 占位是反模式**: 跟 `raise NotImplementedError` 比, `pass` 静默吞错, 排查时极难发现。**所有"以后会实现"的方法都应该 `raise NotImplementedError` + TODO 注释**
