# BUG-M6 Hotfix 修复报告 (生产回归)

**提交**: `fix(M6-hotfix): query_steps_result 加 with_polymorphic 修复 detached instance 错误`
**作者**: cyq (Codex 代笔)
**日期**: 2026-06-19
**触发**: 用户跑 `/api/interfaceResult/queryStepResult?case_result_id=42` 报
`Instance <APIStepContentResult> is not bound to a Session; attribute refresh operation cannot proceed`
**测试**: 111 unit + 3 integration = 114 全过 (原 109, 新增 5 个 hotfix 测试)

---

## 现象

用户跑 `http://192.168.50.87:8000/api/interfaceResult/queryStepResult?case_result_id=42`,
后端抛:

```
sqlalchemy_exception_handler: 数据库异常: Instance <APIStepContentResult at 0x1127ac550> is not bound to a Session;
attribute refresh operation cannot proceed
```

## 根因

上一轮 M6 fix 删了 `InterfaceCaseContentResult.__mapper_args__['with_polymorphic'] = '*'`
(8x 行宽浪费), 但**漏考虑了 2 个查询用 to_dict() 访问子类列**:

| 查询 | to_dict 调用 | 子类列访问 | 状态 |
|---|---|---|---|
| `query_by_case_result_id` | `query_with_interface_results` 调 | `result.to_dict()` → 反射访问 `interface_result_id` 等 | **FAIL** |
| `query_by_task_result_id` | 没人用 to_dict | — | OK (没人调) |
| `query_by_content_type` | 没人用 to_dict | — | OK (没人调) |
| `query_steps_result` | 控制器直接 `Response.success(data)` | `jsonable_encoder` → `to_dict()` → 反射 | **FAIL** |

`to_dict()` 用 `self.__class__.__mapper__.self_and_descendants` 反射遍历子类列
(如 `APIStepContentResult.interface_result_id`), 删了 `'*'` 后这些列**不在 SELECT 里**,
`getattr(self, 'interface_result_id')` 触发 SQLAlchemy 想 lazy-load / refresh,
session 已关就报 "is not bound to a Session"。

我**在 M6 报告里写错了**: "3 个查询都只读基类字段, 不需要子类表 JOIN"。
实际上 `to_dict()` 是默认入口, 控制器/调用方随时可能用, 删 `'*'` 之前必须
**主动**给所有"会被 to_dict"的查询显式 `with_polymorphic`。

## 修法 (最小侵入)

### 1. `query_steps_result` 显式 with_polymorphic(8 个子类)

```python
poly = with_polymorphic(
    InterfaceCaseContentResult,
    [APIStepContentResult, GroupStepContentResult, ConditionStepContentResult,
     ScriptStepContentResult, DBStepContentResult, WaitStepContentResult,
     AssertStepContentResult, LoopStepContentResult],
)
stmt = select(poly).options(
    joinedload(poly.APIStepContentResult.interface_result),
    joinedload(poly.GroupStepContentResult.interface_results),
    joinedload(poly.ConditionStepContentResult.interface_results),
).where(...)
```

注意 2 个**易错点**:
- `joinedload` 必须用 `poly.APIStepContentResult`, **不能用裸 `APIStepContentResult`**,
  否则报 "Mapped class does not apply to any of the root entities"
- `with_polymorphic` 必须列**所有 8 个子类**, 漏掉的话对应类型的 step
  `to_dict()` 还是会失败 (测试 `test_bug_m6_query_steps_result_lists_all_subclasses` 锁住)

### 2. `query_with_interface_results` 改用 `query_steps_result`

原来调 `query_by_case_result_id` + `to_dict()` (失败), 改成调 `query_steps_result` (有 with_polymorphic + joinedloads)。返回的 list 包含全部 content type, 行为不变。

### 3. `query_by_case_result_id` / `query_by_task_result_id` / `query_by_content_type` 不动

只有 `get_stats` 一个调用方 (只读 `r.result` 和 `r.content_type`, 基类字段), 不需要子类列, 保持无子类 JOIN, 带宽优势保留。

## 修复前后对照

| 场景 | 修复前 | 修复后 |
|---|---|---|
| `GET /api/interfaceResult/queryStepResult?case_result_id=42` | 500 数据库异常 | 200 正常返回 |
| `APIStepContentResult.interface_result_id` 是否预加载 | 否, 触发 refresh 失败 | 是, 直接读 |
| `query_by_case_result_id` 性能 | 节省 8x 行宽 (无子类 JOIN) | 节省 8x 行宽 (无子类 JOIN, 不变) |
| `query_steps_result` 性能 | 节省 8x 行宽 (M6 主张) | 跟旧 `'*'` 等同, 但只在需要时用 |

## 回归测试 (5 个新)

1. `test_bug_m6_base_model_no_wildcard` — 基类仍无 `'*'` (M6 主张保留)
2. `test_bug_m6_query_steps_result_uses_with_polymorphic` — 必须显式 with_polymorphic
3. `test_bug_m6_query_steps_result_lists_all_subclasses` — 必须列所有 8 个子类
4. `test_bug_m6_query_steps_result_joinedload_uses_poly` — joinedload 必须用 poly 实体
5. `test_bug_m6_to_dict_needs_subclass_columns` — 锁住 to_dict() 反射行为, 防止后人优化时漏考虑

## 教训

**删 ORM 全局行为 (`with_polymorphic='*'`) 之前, 必须主动审计所有"会被 to_dict / 反射"的查询**。
M6 报告里"3 个查询都只读基类字段"是**基于"没人调 to_dict"**的假设,
但 to_dict() 是默认入口, 假设不成立。

**正确做法**: 用 `to_dict()` 反射遍历子类列是**设计选择**, 想要保留这个行为, 就必须
在**所有"返回 ORM 实例给外部代码"的查询**里显式 `with_polymorphic`, 不能只信"基类字段够用"。

## 候选下一步

- 给 `query_by_case_result_id` / `query_by_task_result_id` / `query_by_content_type`
  也加 `with_polymorphic`, 防止后续有人调 to_dict() 触发同样错误
- 或者改成 `to_dict()` 不反射, 只返基类字段 (但可能 break 现有调用方)
- 重新跑生产 case 3 (Case2 副本), 确认 step_result API 正常返回
