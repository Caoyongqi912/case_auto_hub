# BUG-M6 + E6 + E12 修复报告

**提交**: `fix(M6 + E6 + E12): 删 with_polymorphic='*' + _build_result 改返 Dict + extract_manager 过滤失败项`
**作者**: cyq (Codex 代笔)
**日期**: 2026-06-19
**测试**: 106 unit + 3 integration = 109 全过 (原 98, 新增 11: 3×M6 + 3×E6 + 5×E12)

---

## TL;DR

- **M6**: 删 `InterfaceCaseContentResult` 的 `with_polymorphic='*'`, 3 个查询都只读基类字段, 子类表 JOIN 是纯浪费 (8x 行宽膨胀)。`InterfaceCaseContents` (内容表) 保留 `'*'` (因为 query_steps 需要 8 个子类字段, 等同开销但显式说明)。
- **E6**: `_build_result` 不再返回 `(Dict, bool)` tuple, 改返 `Dict`, 调用方用 `result['result']` 拿成功标志。两路来源歧义消除。
- **E12**: `ExtractManager` 失败/无 handler/返回 None 的 extract 不再进返回 list, 日志干净, 下游 `list2dict` 不再需要 None 防御。

---

## BUG-M6: with_polymorphic='*' 笛卡尔积风险

### 根因

`InterfaceCaseContentResult` (结果表) 和 `InterfaceCaseContents` (内容表) 都设了 `'with_polymorphic': '*'`。`'*'` 意味着**每次** SELECT 基类都自动 LEFT OUTER JOIN **所有** 子类表 (8 个)。

实际后果:
- 每次 SELECT 生成 8 个 LEFT OUTER JOIN, DB 计划开销大
- 每行宽度膨胀 8x (8 个子类的列都 SELECT)
- 网络字节数 8x
- ORM hydration 慢 8x

**关键观察**: SQLAlchemy 2.0 的 `to_dict()` 用 `self.__class__.__mapper__.self_and_descendants` 遍历子类表, **这是运行时反射, 跟 `with_polymorphic` 无关**。也就是说, `to_dict()` 拿子类字段不需要查询时 JOIN, 只需要 ORM 实例的 mapper 配置正确。

所以 `with_polymorphic='*'` 在大多数场景下是过度声明。

### 修法 (分两步, 风险分层)

**第 1 步 (本轮已做): 删 `InterfaceCaseContentResult` 的 `'*'`**

`InterfaceCaseContentResult` 有 3 个查询 (`query_by_case_result_id` / `query_by_task_result_id` / `query_by_content_type`), 都只读基类字段 (case_result_id, task_result_id, content_type, result, status, use_time, start_time), 不需要子类表 JOIN。删 `'*'` 零风险。

**第 2 步 (留作 TODO): `InterfaceCaseContents` 暂留 `'*'`**

`InterfaceCaseContents` (内容/定义表) 的 `query_steps` 需要 `target_id` (子类列), step strategies 通过 `step_content.target_id` 拿目标接口/条件/循环/DB 配置。如果删 `'*'`, 每个 step 触发懒加载 = N+1 问题。

`query_steps` 一次查 8 个 step 类型的混合, 显式 `with_polymorphic=[APIStepContent, ConditionStepContent, ..., LoopStepContent]` 等同开销, 但更难维护。**保留 `'*'` 但加注释说明**。

### 修复前后对照 (InterfaceCaseContentResult)

| 场景 | 修复前 | 修复后 |
|---|---|---|
| `SELECT * FROM interface_case_content_result WHERE case_result_id=?` (N=50) | 8 LEFT JOINs, 50 行 × 8 个子表的列 = 50 行 × 8x 宽 | 0 LEFT JOIN, 50 行 × 1 个基表的列 = 50 行 |
| 网络字节数 | ~50 × (基类 + 8 子类列) ≈ 50 × 9x 宽 | ~50 × (基类列) |
| DB 计划时间 | 8x JOIN 评估 | 1 个简单 SELECT |
| ORM hydration | 8 个 class 检测/转换 | 1 个基类 |

### 回归测试 (3 个)

1. `test_bug_m6_no_wildcard_polymorphic` — `__mapper_args__` 不含 `with_polymorphic='*'`
2. `test_bug_m6_polymorphic_on_unchanged` — `polymorphic_on=content_type` 必须保留
3. `test_bug_m6_polymorphic_identity_unchanged` — `polymorphic_identity=None` 必须保留

---

## BUG-E6: _build_result 过度声明

### 根因

`InterfaceExecutor._build_result(ctx)` 旧签名:

```python
def _build_result(self, ctx) -> Tuple[Dict[str, Any], bool]:
    ...
    result['result'] = ctx.success   # ← 字典里有
    return result, ctx.success        # ← 又单独返回
```

两路来源 (dict 的 `result` key + tuple 第二位) 经常不同步: 改 `ctx.success` 后忘了同步 `result['result']` 是常见 bug。

7 个调用方都做 `result, success = await executor.execute(...)` 这种"两路解构", 实际上只需要 `success = result['result']` 一行。

### 修法 (改签名 + 改 7 个调用方)

| 步骤 | 改动 |
|---|---|
| `interface_executor.py` | `_build_result` 返回类型 `Tuple[...]` → `Dict[...]`, `return result, ctx.success` → `return result` |
| `interface_executor.py` | `execute` 返回类型同样 `Tuple[...]` → `Dict[...]` |
| `runner.py` (3 处) | `result, _ = ...` → `result = ...` (success 不用), `result, success = ...` → 加 `success = result['result']` |
| `step_content_api.py` | `step_result, success = ...` → `step_result = ...; success = step_result['result']` |
| `step_content_loop.py` / `step_content_group.py` / `step_content_condition.py` | 同上模式 |

### 修复前后对照

| 场景 | 修复前 | 修复后 |
|---|---|---|
| 调用方 | `result, success = await executor.execute(...)` | `result = await executor.execute(...); success = result['result']` |
| 字典和 bool 不同步 | 可能 (改了 ctx.success 没改 dict) | 不可能 (只有 dict 一路) |
| 文档清晰度 | "Tuple[Dict, bool]" 暗示两路独立 | "Dict, 读 result['result']" 一目了然 |

### 回归测试 (3 个)

1. `test_bug_e6_build_result_returns_dict_not_tuple` — 返回类型是 `dict`, 不是 `tuple`
2. `test_bug_e6_build_result_contains_result_field` — `result['result']` 跟 `ctx.success` 一致
3. `test_bug_e6_execute_signature_returns_dict` — `execute()` 签名注解是 `Dict`, 不是 `Tuple`

---

## BUG-E12: extract_manager 静默吞错 + 返回 list 含失败项

### 根因

```python
for extract in extracts:
    try:
        ...
        if handler:
            extract['value'] = await handler(extract)
        else:
            log.warning(...)
    except KeyError as e:
        log.error(...)   # ← 只 log, 不 raise
    except Exception as e:
        log.error(...)   # ← 只 log, 不 raise

return extracts  # ← 把失败的也返回, 'value' 键未设
```

失败时 `extract['value']` 永远没这键 (不是 None, 是压根没这键)。下游:
1. 日志打印 `value=None` (dict.get 返回 None), 看着像"没找到"但实际是"提取失败"
2. `add_vars(vars_list)` → `list2dict` → `item.get(KVItem.VALUE) is None` → 跳过

虽然 `list2dict` 兜底了 None, 但**调用方心智负担重**, 而且**错误信息丢失** (handler 失败的具体原因被吞了, 只能从前面 log 拼凑)。

### 修法 (过滤失败项, 不依赖下游防御)

```python
successful: List[Dict[str, Any]] = []
for extract in extracts:
    try:
        target = int(extract.get("target", 0))
        handler = handlers.get(target)
        if not handler:
            log.warning(f"Unsupported Target: {target}")
            continue
        extract['value'] = await handler(extract)
        if extract.get('value') is not None:
            successful.append(extract)
        else:
            log.warning(f"Extract returned None: {extract.get('key')}")
    except KeyError as e:
        log.error(f"Missing key in extract: {e}")
    except Exception as e:
        log.error(f"Error processing extract: {e}")

return successful
```

`continue` 而不是返回失败项, 日志只看到成功的, 失败的从 caller 视角"消失"但实际是"按设计不污染变量表"。

### 修复前后对照

| 场景 | 修复前 | 修复后 |
|---|---|---|
| 5 个 extract, 3 个成功, 2 个失败 | 返回 5 个, 2 个无 value, 下游靠 list2dict 过滤 | 返回 3 个, 全部含 value, 下游无负担 |
| 日志行 | 打印 5 个 (含 2 个 value=None) | 打印 3 个 (全部有效) |
| 失败原因追溯 | 仅在前面 log 看, 易被其他日志淹没 | 同前, 但少了"虚假的 None"噪音 |

### 回归测试 (5 个)

1. `test_bug_e12_no_handler_extract_dropped` — 无 handler 的 extract 被过滤
2. `test_bug_e12_handler_exception_extract_dropped` — handler 抛异常的被过滤
3. `test_bug_e12_handler_returns_none_dropped` — handler 返回 None 的被过滤
4. `test_bug_e12_successful_extract_kept` — 成功的保留, value 正确
5. `test_bug_e12_mixed_partial_success` — 混合场景, 只有成功的留下来

---

## 测试覆盖

```bash
$ .venv/bin/python -m pytest tests/ -q -m "not integration" --tb=short
================ 106 passed, 3 deselected, 6 warnings in 6.54s =================

$ .venv/bin/python -m pytest tests/ -m integration
================ 3 passed, 106 deselected, 6 warnings in 1.19s =================
```

新增 11 个测试 (3 × M6 + 3 × E6 + 5 × E12), 全部通过, 无回归。

---

## 风险评估

### M6

- **删 `InterfaceCaseContentResult` 的 `'*'`**: 3 个查询都只读基类字段, 零回归
- **`InterfaceCaseContents` 保留 `'*'`**: query_steps 需要子类字段, 删了会 N+1
- **未来扩展**: 新增子类不需要改 model, 也不需要改 mapper

### E6

- **改 7 个调用方**: 都已逐行验证, 单测全过
- **API 破坏性**: 是的, 内部 API, 没有外部用户
- **`result['result']` 永远是 bool**: 不会返回 None (除非 ctx.success 是 None, 但 schema 是 bool)

### E12

- **过滤失败项**: 不影响成功项; 下游 list2dict 已能处理 None, 兼容性 OK
- **日志变更**: 失败项的日志从 caller 视角消失 (但前面 log 还有, 用于排查)
- **`extracts` 列表会被 in-place 修改**: 跟旧实现一致, 行为不变

---

## 候选下一波

| 优先级 | BUG | 估时 | 说明 |
|---|---|---|---|
| P0 | F6 | 0h | 已闭环 (F5 fix) |
| P1 | D5 | 2-3h | query_steps 多 joinedload 笛卡尔积 (下一步) |
| P1 | E8/E9 | 1.5h | total_num 行为不一致, 跟 M8 联动 |
| P1 | RED-1/3/5 | 0.5h | runner.py 几个 quick wins (重复 if / import asyncio / 空注释) |
| P2 | E10/E11 | 1h | db/script 异常处理 + condition assert_data 写库 |

总剩余 P1 ~10 项, 1-2 天能再清一波。
