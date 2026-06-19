# BUG-F8 修复报告 — `result_writer` 模块级单例死灰复燃

> 状态: ✅ 已修复
> 修复提交: (待 commit)
> 涉及文件: 13 个
> 新增测试: 16 个 (全部通过)
> 数据库回填: 1 条 (case_result=42)

---

## 1. 问题发现

`/api/interfaceResult/queryStepResult?case_result_id=42` 返回 0 条 step_result,
但 `interface_case_result.id=42` 在库里存在 (`fail_num=1`, 案例确实跑过且失败)。

直接证据:

```sql
SELECT COUNT(*) FROM interface_case_content_result WHERE case_result_id = 42;
-- 0
SELECT id, content_result_id FROM interface_result ORDER BY id DESC LIMIT 1;
-- 133, NULL    ← interface_result 入库了, 但 content_result_id 是 NULL
```

interface_log 里看到 step 1 跑了、报 `Illegal header name b' 3'`、正常 FINISH,案例正常结束。
但 `interface_case_content_result` 0 行 —— **数据在执行过程中被静默丢失**。

---

## 2. 根因分析 (BUG-D1 修复不闭环)

### 2.1 修复历史

| 修复 | commit | 修复内容 |
|---|---|---|
| D1 | `d4b4daa` | `InterfaceRunner` 自建 `ResultWriter` 实例, `finally` 清缓存 |

D1 修复目标是避免模块级单例在并发 case 时缓存互相污染。
**但 D1 只改了 `runner.py`, 没有改 8 个 `step_content_*.py` + `task.py` + `play_interface_strategy.py`**,
这 10 个文件仍然:

```python
from croe.interface.writer import result_writer  # ← 模块级单例!
...
await result_writer.write_step_result(STEP_API, ...)  # 进单例的 cache
```

### 2.2 数据流断点

`step_content_api.py:execute` (修复前):

```
case_result (DB) ←── init_case_result 走 runner 实例 (✅)
interface_result (DB) ←── write_interface_result(immediate=True) 走模块单例 (✅, 直接 insert)
content_result (DB) ←── write_step_result(STEP_API) 走模块单例 ❌
                          └─→ 进单例的 content_result_cache
                          └─→ finalize_case_result flush 的是 runner 实例的空 cache
                          └─→ 单例 cache 永远不被 flush
                          └─→ 进程退出, 数据丢失
```

### 2.3 影响范围

- **8 个 step_content_*.py** 写 STEP_API / STEP_API_GROUP / STEP_API_CONDITION / STEP_LOOP 全部走单例
- **子步骤 api_result** (loop/group/condition 内部调 `write_interface_result`) 走单例的 cache
- **task.py** 任务级 `init_task_result` / `finalize_task_result` 走单例 (虽然不走 cache,
  但 `finalize_task_result` 调 `_flush_cache` 时会把别人数据冲掉)
- **play_interface_strategy.py** 走单例 (但它只 `immediate=True`, 实际安全)

直接受害者: `case_result=42` (D1 修复前跑的数据), 修复后所有新 case 都受影响。

---

## 3. 修复方案

### 3.1 设计原则

`result_writer` 是有状态对象 (持有 cache + mapper), 不能用模块单例。
应当跟随所属的"执行上下文", 由 `ExecutionContext` 持有并向下传递。

### 3.2 改动清单

| 文件 | 改动 |
|---|---|
| `croe/interface/executor/context.py` | `ExecutionContext` 新增 `result_writer: ResultWriter` 字段; `CaseStepContext` 新增 `.result_writer` 便捷 property |
| `croe/interface/runner.py` | `run_interface_case` 创建 `ExecutionContext` 时传入 `self.result_writer` |
| `croe/interface/executor/step_content/step_content_api.py` | `result_writer.xxx` → `step_context.result_writer.xxx` (3 处) |
| `croe/interface/executor/step_content/step_content_group.py` | 同上 (4 处) |
| `croe/interface/executor/step_content/step_content_condition.py` | 同上 (10 处) |
| `croe/interface/executor/step_content/step_content_loop.py` | 同上 (4 处) |
| `croe/interface/executor/step_content/step_content_assert.py` | 同上 (1 处) |
| `croe/interface/executor/step_content/step_content_db.py` | 同上 (1 处) |
| `croe/interface/executor/step_content/step_content_script.py` | 同上 (1 处) |
| `croe/interface/executor/step_content/step_content_wait.py` | 同上 (1 处) |
| `croe/interface/writer/__init__.py` | **删除模块级单例** `result_writer = ResultWriter()` |
| `croe/interface/task.py` | `TaskRunner.__init__` 创建 `self.result_writer = ResultWriter()`; 3 处单例调用改 `self.result_writer.xxx` |
| `croe/play/executor/step_content_strategy/play_interface_strategy.py` | 局部 `rw = ResultWriter()` 替代单例 (play 路径只有 1 处 `immediate=True` 调用) |
| `tests/croe/interface/test_bug_f8_result_writer_in_context.py` | **新增** 16 个回归测试 |
| `tests/croe/interface/_bug_ids.py` | 新增 `BUG_F8` 常量 |

### 3.3 关键代码 (修复后)

`context.py:ExecutionContext`:

```python
@dataclass
class ExecutionContext:
    interface_case: "InterfaceCase"
    env: "EnvModel"
    case_result: "InterfaceCaseResult"
    # BUG-F8 修复: result_writer 注入上下文, 替代模块级单例
    result_writer: "ResultWriter"   # ← 新增
    task_result: Optional["InterfaceTaskResult"] = None
```

`runner.py:175-181`:

```python
# BUG-F8 修复: 把 runner 自有 result_writer 注入上下文
execution_context = ExecutionContext(
    interface_case=interface_case,
    env=target_env,
    case_result=case_result,
    result_writer=self.result_writer,   # ← 新增
    task_result=task_result
)
```

`step_content_api.py` (其他 7 个 step_content 文件同模式):

```python
async def execute(self, step_context: CaseStepContext) -> bool:
    ...
    interface_result = await step_context.result_writer.write_interface_result(  # ← 改前: result_writer.xxx
        interface_result=InterfaceResult(**step_result),
        immediate=True
    )
    ...
    await step_context.result_writer.write_step_result(  # ← 改前: result_writer.xxx
        content_type=CaseStepContentType.STEP_API,
        ...
    )
```

`writer/__init__.py` (单例删除):

```python
from .result_writer import ResultWriter
# BUG-F8 修复: 删掉模块级单例 result_writer
# (原 D1 修复不闭环, 8 个 step_content_*.py + task.py 仍 import 这个单例,
#  导致 STEP_API content_result_cache 永远不被 flush)
__all__ = ['ResultWriter']
```

---

## 4. 验证

### 4.1 测试

```
$ pytest tests/ -q --ignore=tests/integration
======================== 74 passed, 6 warnings in 6.24s ========================
```

| 测试套件 | 通过 | 说明 |
|---|---|---|
| 老 58 个测试 | 58/58 | D1/D2/D4/M5/F1-F4/M1-M3/V1/M11/D7/D8/F7/RED-D5 全过 |
| F8 16 个测试 | 16/16 | 见 §4.2 |
| 集成测试 | 2/2 | `test_run_interface_case_smoke.py` |

### 4.2 F8 回归测试覆盖 (16 个)

```
test_bug_f8_writer_init_does_not_export_singleton
  → AST 校验 writer/__init__.py 没有 `result_writer = ResultWriter()`
test_bug_f8_no_module_singleton_import[step_content_api.py]
test_bug_f8_no_module_singleton_import[step_content_group.py]
test_bug_f8_no_module_singleton_import[step_content_condition.py]
test_bug_f8_no_module_singleton_import[step_content_loop.py]
test_bug_f8_no_module_singleton_import[step_content_assert.py]
test_bug_f8_no_module_singleton_import[step_content_db.py]
test_bug_f8_no_module_singleton_import[step_content_script.py]
test_bug_f8_no_module_singleton_import[step_content_wait.py]
test_bug_f8_no_module_singleton_import[task.py]
test_bug_f8_no_module_singleton_import[play_interface_strategy.py]
  → 这 10 个文件不能 import 模块单例 (AST 扫描源码)
test_bug_f8_execution_context_has_result_writer
  → ExecutionContext 必须有 result_writer 字段
test_bug_f8_case_step_context_has_result_writer_property
  → CaseStepContext 必须有 result_writer property
test_bug_f8_runner_injects_result_writer_into_context
  → runner.py 必须有 `result_writer=self.result_writer`
test_bug_f8_task_runner_has_own_result_writer
  → TaskRunner.__init__ 必须有 `self.result_writer = ResultWriter()`
test_bug_f8_runner_result_writer_is_same_as_context
  → 端到端: ExecutionContext.result_writer is runner.result_writer
```

### 4.3 E2E 验证

通过 ORM 直接跑 case 3 (case 标题 "Case2(副本)"):

```
跑完: success=False, case_result_id=44
runner.result_writer.cache: api=0, content=0
[断言] interface_case_content_result 返回 1 条:
  - id=153 case_result_id=44 content_type=1 result=False name=randomName
*** BUG-F8 修复验证通过 ***
```

修复前后对比:

| case_result_id | 修复前 content_result 行数 | 修复后 |
|---|---|---|
| 42 (D1 修复前跑的) | 0 | 0 (历史数据, 见 §5 回填) |
| 44 (F8 修复后跑的) | — | 1 ✓ |

DB 验证:

```sql
SELECT id, case_result_id, content_id, content_type, content_name, result, status
FROM interface_case_content_result WHERE case_result_id IN (42, 44);
+-----+----------------+------------+--------------+--------------+--------+--------+
| id  | case_result_id | content_id | content_type | content_name | result | status |
+-----+----------------+------------+--------------+--------------+--------+--------+
| 153 |             44 |         12 | STEP_API     | randomName   |      0 | FAIL   |
| 154 |             42 |         12 | STEP_API     | randomName   |      0 | FAIL   |  ← 回填
+-----+----------------+------------+--------------+--------------+--------+--------+
```

---

## 5. 历史数据回填

`case_result=42` 是修复前跑的数据, content_result 永久丢失 (进程退出后内存里的单例 cache
就没了)。已用 SQL 重建一条最低限度的失败记录, 关联到原 `interface_result.id=133`:

```sql
-- 详见 /tmp/backfill_f8.sql
INSERT INTO interface_case_content_result (case_result_id, content_id, ...)
SELECT 42, assoc.interface_case_content_id, ...
FROM interface_case_content_association assoc
JOIN interface_case_result cr ON cr.interface_case_id = assoc.interface_case_id
WHERE cr.id = 42;

INSERT INTO interface_case_content_result_api (result_id, interface_result_id)
SELECT 新插入的.id, 133 FROM interface_case_content_result WHERE case_result_id = 42;
```

回填后 API 行为:

```
$ curl /api/interfaceResult/queryStepResult?case_result_id=42
# 返回 1 条 step_result (status=FAIL, content_name=randomName)
```

---

## 6. 后续可考虑 (本 PR 范围外)

1. **`interface_result.content_result_id` 仍是 NULL** (新 case 也一样):
   `step_content_api.py` 先 `write_interface_result(immediate=True)`, 再 `write_step_result(STEP_API)`。
   前者入库时 `content_result_id` 还没生成, 反向 FK 没回填。
   建议在 `write_step_result` 返回 content_result_id 后, 再去 update `interface_result.content_result_id`。
   影响: `interface_result` 详情页的 `content_result_id` 字段为 null, 业务功能可降级。

2. **`_flush_cache` 失败时 cache 被清空 (D4 留的 TODO)**:
   D4 修复里 bulk 失败时回退到逐条, 但 cache 在 `finally` 仍被清掉, 失败数据没重试。
   建议加 retry queue。

3. **`starter.over` 当前返回 None, task 模式调用方要 `success, _ = ...` 才能 unpack**:
   F2 修复已加注释, 但语义不优雅。可考虑改成返回 `(success, case_result)` 元组。

---

## 7. 关联 BUG 列表

| BUG | 状态 | 说明 |
|---|---|---|
| BUG-D1 | 部分修复 (本 PR 闭环) | runner 自有 result_writer ✓, 但 8 个 step_content_*.py 没用上 ✗ → F8 |
| BUG-F8 | ✅ 本 PR 新修复 | result_writer 注入 ExecutionContext, 干掉模块单例 |
