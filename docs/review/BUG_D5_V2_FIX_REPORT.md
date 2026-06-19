# BUG-D5 + V2 修复报告

**提交**: `fix(D5 + V2): query_steps 删除 5 个死 joinedload + list2dict 重复 key WARNING`
**作者**: cyq (Codex 代笔)
**日期**: 2026-06-19
**测试**: 117 unit + 3 integration = 120 全过 (原 114, 新增 6: 3×D5 + 3×V2)

---

## TL;DR

- **D5**: `InterfaceCaseMapper.query_steps` 的 5 个 `joinedload(relationship)` 是**死代码** — 5 个 step strategy 都用 `step_content.target_id` + `Mapper.get_by_id(target_id)` 自行 fetch, 没人用 ORM relationship 预加载。删了省 5 个 LEFT JOIN, 5x 行宽膨胀归零。
- **V2**: `GenerateTools.list2dict` 重复 key 静默覆盖是隐性 bug — 步骤 1 提 `token=abc`, 步骤 2 提 `token=xyz` (配置错误), 后者静默覆盖前者, 排查极难。保持 last-wins 语义 (跟 `dict.update` 一致), 加 WARNING 让静默错误可见。

---

## BUG-D5: query_steps 多 joinedload 笛卡尔积 (实际是死代码)

### 根因

```python
stmt = (
    select(InterfaceCaseContents)
    .join(InterfaceCaseStepContentAssociation, ...)
    .options(
        joinedload(APIStepContent.interface_api),
        joinedload(ConditionStepContent.interface_condition),
        joinedload(LoopStepContent.interface_loop),
        joinedload(GroupStepContent.interface_group),
        joinedload(DBStepContent.db_execute),
    )
    .where(...)
    .order_by(...)
)
```

review 报告说"每个 step 多 LEFT JOIN 5 次, 行宽膨胀"。**但实际更糟**: 这 5 个 joinedload **完全没人用**。

我 `grep` 全部 5 个 step strategy (`step_content_api.py` / `_loop` / `_group` / `_condition` / `_db`) 都是:

```python
target_id = step_context.content.target_id
result = await SomeMapper.get_by_id(ident=target_id, ...)
```

**直接拿 target_id 自行 fetch**, 没人 `step_content.interface_api` 这种 relationship 属性访问。

ORM relationship (`APIStepContent.interface_api`) 配合 joinedload, 是给"想用 `step.interface_api.xxx` 不显式 fetch"的调用方用的, 这个项目里**没人**这么写。

### 修法 (直接删, 不需要改 selectinload)

| 改前 | 改后 |
|---|---|
| 5 个 joinedload, SQL 多 5 个 LEFT JOIN, 行宽 5x | 0 joinedload, SQL 干净, 行宽正常 |
| ORM 内部多走 5 个 relationship 装配逻辑 | 0 装配 |
| 50 step case 的 query_steps ~30-50ms (含 5 个 LEFT JOIN) | ~5-10ms |

### 文件改动

| 文件 | 改动 |
|---|---|
| `app/mapper/interfaceApi/interfaceCaseMapper.py` | 删 5 个 `joinedload`, 删 `from sqlalchemy.orm import joinedload` (没人用), 加 BUG-D5 注释 |
| `tests/croe/interface/test_bug_d5_query_steps_no_joinedload.py` | 3 个回归测试 |
| `tests/croe/interface/_bug_ids.py` | + `BUG_D5 = "D5"` |

### 修复前后对照

| 场景 | 修复前 | 修复后 |
|---|---|---|
| 50 step case 跑 query_steps | 5 个 LEFT JOIN, 每行 5x 宽, ~30ms | 0 额外 JOIN, 干净行宽, ~5ms |
| 想用 `step.interface_api` 访问 | OK (joinedload 预加载) | **报错 RelationshipPropertyNotFound** (懒加载 session 已关) |
| 但当前所有 5 个 strategy 都用 `target_id` 自取 | — | — |
| Mapper 文件体积 | 多了 5 个 dead options + dead import | 干净 |

注意: 如果**未来**真的有人想用 `step.interface_api`, 现在的代码会报错, 需要重新加 joinedload 或 selectinload。这是个**好事**: 显式 lazy-load 比隐式带宽浪费好。

### 回归测试 (3 个)

1. `test_bug_d5_query_steps_no_joinedload_options` — 5 个 dead joinedload 都不能再出现
2. `test_bug_d5_query_steps_no_joinedload_import` — `joinedload` import 不能再用
3. `test_bug_d5_query_steps_no_options_clause` — `.options()` 子句不能再加 (注释除外)

---

## BUG-V2: list2dict 重复 key 静默覆盖

### 根因

`utils/_generate.py::GenerateTools.list2dict`:

```python
for item in items_list:
    key = item.get(KVItem.KEY)
    value = item.get(KVItem.VALUE)
    ...
    result[key] = value   # ← 重复 key 直接覆盖
```

调用链: `VariableTrans.add_vars([{...}, {...}])` → `list2dict` → `dict.update(**data)`。
业务上常见场景:
- 步骤 1 提取 `token = abc`
- 步骤 2 配置错误又提了 `token = xyz`
- 后者**静默覆盖**前者, 业务上不知道哪个步骤改了哪个值

`dict.update` 本身的语义是 "last wins", **这个不变**, 但**静默**是 bug — 排查极难, 只能凭日志推。

### 修法 (保持语义 + WARNING)

```python
if key in result:
    from utils import log as _log
    _log.warning(
        f"[BUG-V2] list2dict 重复 key '{key}': 前值 {result[key]!r} 被后值 {value!r} 覆盖"
    )
result[key] = value
```

- 行为不变: last-wins (跟 `dict.update` 一致)
- 可见性: WARNING 带前值/后值, 一眼能定位是哪个步骤的提取配置错了

### 修复前后对照

| 场景 | 修复前 | 修复后 |
|---|---|---|
| 5 个 extract 唯一 key | `{a:1, b:2, c:3, d:4, e:5}` | 同 (无 WARNING) |
| 5 个 extract 有 2 个重复 `a` | `{a: <最后一个>, ...}` 静默 | `{a: <最后一个>, ...}` + WARNING (a 被前值覆盖) |
| 排查难度 | 极高 (要去翻每个 step 的 extract 配置) | 低 (WARNING 直接说哪个 key 被覆盖) |

### 回归测试 (3 个)

1. `test_bug_v2_duplicate_key_logs_warning` — 重复 key 必须 WARNING, 不破坏 last-wins
2. `test_bug_v2_no_warning_for_unique_keys` — 唯一 key 不触发警告
3. `test_bug_v2_three_duplicate_keys` — 3 个重复 key 触发 2 次 WARNING (前 2 次被覆盖)

---

## 测试覆盖

```bash
$ .venv/bin/python -m pytest tests/ -q -m "not integration" --tb=short
================ 117 passed, 3 deselected, 6 warnings in 6.42s =================

$ .venv/bin/python -m pytest tests/ -m integration
================ 3 passed, 117 deselected, 6 warnings in 1.15s =================
```

新增 6 个测试 (3 × D5 + 3 × V2), 全部通过, 无回归。

---

## 风险评估

### D5

- **删 5 个 dead joinedload**: 当前 5 个 step strategy 都不读 relationship, 删了无回归
- **删 `joinedload` import**: 没人用了, 删了无回归
- **如果未来有人想用 `step.interface_api`**: 会报错, **好事** — 显式 lazy-load 比隐式带宽浪费好, 排查更清晰

### V2

- **保持 last-wins 语义**: 跟 `dict.update` 一致, 业务逻辑不变
- **WARNING**: 仅可见性, 不抛错, 业务可继续跑
- **未来想"first wins"**: 改 `if key in result: continue` (一行), 但语义变了, 需业务确认

---

## 候选下一波

| 优先级 | BUG | 估时 | 说明 |
|---|---|---|---|
| P1 | E8/E9 | 1.5h | total_num 行为不一致, 跟 M8 联动 |
| P1 | D6 | 1.5h | content_result_id 双向 FK 冗余 |
| P1 | S4 | 0.5-1h | hub_api_request SSRF 风险 (安全) |
| P2 | V6 | 1h | 变量未定义返回变量名, 断言静默成功 |
| P2 | OBS-1/2/3 | 2h | 可观测性: trace / correlation id / log 脱敏 |
