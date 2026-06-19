# BUG-V6 Fix Report: 引用未定义变量时静默返回变量名

**触发版本**: master (V6 之前)
**风险面**: 高 — 静默错, 排查极难
**Commit**: (本 fix)
**测试**: `tests/utils/test_bug_v6_undefined_variable_warning.py` (7 个)

---

## 现象 (理论攻击/坑)

`utils/variableTrans.py:_resolve_vars` 跟 `get_var` 都有同样的兜底 bug:

```python
# _resolve_vars (line 144)
return self._vars.get(var_name, f"{var_name}")  # ← 缺失 → 返回 "var_name" 字符串

# get_var (line 73)
return self._vars.get(key, key)  # ← 缺失 → 返回 key 字符串
```

调用方拿到的不是 None / 报错, 而是变量名的字面字符串。后果:

| 场景 | 用户写 | 上游 extract 失败时实际发出 |
|---|---|---|
| URL 拼接 | `http://api/users/{{user_id}}/profile` | `http://api/users/user_id/profile` (404) |
| Header | `Authorization: Bearer {{token}}` | `Authorization: Bearer token` (401) |
| Body JSON | `{"page": "{{page_idx}}"}` | `{"page": "page_idx"}` (类型错) |
| 断言 | `assert response.id == {{user_id}}` | 永远 False, 静默挂 |

操作员拿到 404/401/类型错, **误以为是 API 挂** (实际是变量没提取到)。E12 修了 extract handler 返回 None 不进 vars_list, 但下游 `trans()` 仍然拿不到变量, 这个静默错就暴露了。

---

## 修复

两个函数都加 WARNING 兜底 + 严格模式逃生口:

```python
# _resolve_vars
if var_name not in self._vars:
    msg = f"[BUG-V6] 引用了未定义的变量 '{var_name}', 将按字面量返回"
    if os.environ.get("VARIABLE_TRANS_STRICT") == "1":
        raise KeyError(msg)
    log.warning(msg)
return self._vars.get(var_name, f"{var_name}")

# get_var 同样模式
if key not in self._vars:
    msg = f"[BUG-V6] get_var 未定义变量 '{key}'"
    if os.environ.get("VARIABLE_TRANS_STRICT") == "1":
        raise KeyError(msg)
    log.warning(msg)
return self._vars.get(key, key)
```

---

## 设计取舍

| 选项 | 取舍 |
|---|---|
| **(A) 抛 KeyError 直接挂** | 严格, 但破坏存量 case (很多 "碰巧能跑" 的 case 实际有未定义变量) |
| **(B) 返 None** | 改语义, 字符串拼接里 None 变 "None" 同样错, 但更难看 |
| **(C) 保持返变量名 + WARNING** ✅ | 不破坏存量, 运维可 grep WARNING 定位问题 |
| **(D) 严格模式 ENV 开关** ✅ | 渐进式迁移, 配合 (C) 用, 后期可全量切 |

选 (C) + (D) 组合:
- **默认**: WARNING 出来, 行为不变, 存量 case 继续跑
- **VARIABLE_TRANS_STRICT=1**: 严格模式, 缺失变量直接 KeyError 让 case 立刻挂
- 运维迁移路径: 先看 WARNING 数量 → 修 extract → 全量开 STRICT

---

## 修复前后对照

| 调用 | 修复前 | 修复后 (默认) | 修复后 (STRICT=1) |
|---|---|---|---|
| `{{user_id}}` 缺失 | 返 `"user_id"`, 无日志 | 返 `"user_id"`, WARNING 含 var_name | 抛 KeyError, case 挂 |
| `get_var("missing")` | 返 `"missing"`, 调用方易误判 | 返 `"missing"`, WARNING | 抛 KeyError |
| 已定义变量 | 正常 | 正常 | 正常 |
| `$f_xxx` / `$g_xxx` | 走 faker / global | 同上 (不影响) | 同上 (不影响) |

---

## 回归测试 (7 个, 不接 DB)

`tests/utils/test_bug_v6_undefined_variable_warning.py`:

1. `test_bug_v6_resolve_undefined_var_returns_name_with_warning` — 核心: 缺失变量仍返 name, 但 WARNING 出来
2. `test_bug_v6_resolve_defined_var_no_warning` — 已定义变量不 WARNING
3. `test_bug_v6_resolve_f_prefix_still_works` — `$f_` 前缀仍走 faker, 不进 V6 警告分支
4. `test_bug_v6_resolve_g_prefix_still_works` — `$g_` 前缀仍走 `_find_g_vars`
5. `test_bug_v6_get_var_undefined_returns_key_with_warning` — get_var 同病
6. `test_bug_v6_get_var_defined_no_warning` — get_var 已定义不 WARNING
7. `test_bug_v6_strict_mode_raises_keyerror` — `VARIABLE_TRANS_STRICT=1` 抛 KeyError

**全量回归**: 153 unit passed (146 老 + 7 新), 0 fail.

---

## 教训

- **静默默认值是隐性炸弹**: 任何 `dict.get(key, default)` 的 default 都该想清楚 — "返回 key 名字符串" 这种"看似合理"的兜底, 实际把"出错" 变成 "看似正常但用错值"。遇到 default 一定要: 1) log warning 留痕 2) 留环境变量切严格模式
- **E12 + V6 联动**: E12 修了 extract manager 过滤掉失败项 (不再返 None), 但下游 `trans()` 仍然处理"拿不到"的情况, 这就是 E12 当时没堵到的口子。**修上游时主动看下游所有用到结果的地方**, 否则只是把 bug 推到下游静默
- **E6 同病**: _build_result 旧签名返 `(Dict, bool)` 跟 result dict 里的 'result' 字段两路来源 — 跟 V6 "两路兜底" 同模式, 统一为单源 + 强类型
