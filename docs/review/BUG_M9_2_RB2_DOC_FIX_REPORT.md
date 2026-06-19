# BUG M9-2 + RB2 + DOC 修复报告

**修复时间**: 2026-06-20
**HEAD**: f5d5a8a → (本批 commit)
**回归测试**: 398 passed, 1 skipped, 3 deselected, 0 fail (+6 新, +0 改写)
**触发源**: f5d5a8a 后对 `croe/interface` 流程 + model + mapper 三层深度 code review 发现的 4 个 P0 隐藏 BUG 中, 本批修 3 个 (跳 1 个)。

## 0. TL;DR

| BUG | 文件 | 现象 | 修法 |
|---|---|---|---|
| **M9-2** | `croe/interface/writer/result_writer.py:255` | `status` 写 `"SUCCESS"/"FAIL"` 字面量, 跟 M9 修的 8 个 step_content 不一致; status 列改 enum 类型会静默写错 | 统一走 `StepStatusEnum.SUCCESS / .FAIL` |
| **RB2** | `croe/interface/runner.py:298` | `run_interface_by_task` 漏调 `init_global_headers()`, 任务执行时 g_headers 永远 `[]`, 全局 header 全部丢失 | 函数体开头加 `await self.init_global_headers()`, 跟另外 3 个入口对齐 |
| **DOC** | `app/mapper/interfaceApi/interfaceResultMapper.py:recompute_case_result_nums` | `session=None` 直接 raise `ValueError`, 但 docstring + 调用方注释 (result_writer.py:367) 都写"自管事务", 实际静默 except 丢对账 | session=None 时开自己的 `cls.transaction()`, 跟 D4 哲学一致 |

**不修本批**: BUG-D4-V2 partial commit (interfaceResultMapper.py:229-238 + 349-355 的显式 `session.commit()`), 等独立一锅端。

## 1. BUG-M9-2 详情

### 1.1 根因

`result_writer.py:255` 旧代码:
```python
'status': "SUCCESS" if success else "FAIL",
```

`croe/interface/executor/step_content/step_content_*.py` 8 个文件 (api / assert / condition / db / group / loop / script / wait) 在 M9 批次已经全改成 `StepStatusEnum.SUCCESS / .FAIL`。**M9 漏改了 result_writer 的 cache flush 路径**。

### 1.2 后果

- 现在: status 列是 `String(10)`, 写 `"SUCCESS"` / `"FAIL"` 表面 OK, 但跟 step_content 写法不一致, 后续读 `case_result.status` 时类型不一致 (str vs enum)。
- 上线炸: status 列改成 `Enum(StepStatusEnum, native_enum=False, length=20)` 时, 写 `"SUCCESS"` 字符串会被 SQLAlchemy 当成"不在 enum 值列表里"抛 `LookupError` (在用户已踩过的 EnumMigration 路径上)。

### 1.3 修法

`croe/interface/writer/result_writer.py:29` 加 import:
```python
from enums import InterfaceAPIStatusEnum, InterfaceAPIResultEnum, StepStatusEnum  # BUG-M9-2
```

`result_writer.py:255` 改:
```python
'status': StepStatusEnum.SUCCESS if success else StepStatusEnum.FAIL,
```

### 1.4 为什么不改方案 B (改成 f-string 拼 enum 名)

`StepStatusEnum.SUCCESS.name` 也行, 但 `StepStatusEnum.SUCCESS` enum 实例直接进 SQLAlchemy 时会按 `Enum(StepStatusEnum, ...)` 列定义自动转字符串, 更直白。

### 1.5 锁住测试 (`tests/croe/interface/test_bug_m9_2_rb2_doc_batch.py`)

- `test_bug_m9_2_result_writer_status_uses_step_status_enum`: 用 regex 提取 `result_data = {...}` 块, 在块内匹配 `"SUCCESS"` / `"FAIL"` 字面量 + 解析 `status` 行的 RHS 必须是 `StepStatusEnum.*`。**只在块内匹配, 避免误命中 docstring / 修复注释里"SUCCESS/FAIL"这两个词的引用**。
- `test_bug_m9_2_step_content_status_consistency`: 8 个 step_content 模块写过 status 的, 必须用 `StepStatusEnum`, 跟 result_writer 写法对齐。

## 2. BUG-RB2 详情

### 2.1 根因

`croe/interface/runner.py` 4 个执行入口:

| 入口 | 行号 | 调 `init_global_headers`? |
|---|---|---|
| `try_interface` | 78 | ✅ |
| `try_group` | 103 | ✅ |
| `run_interface_case` | 169 | ✅ |
| `run_interface_by_task` | 298 | ❌ **漏了** |

`init_global_headers` 作用: 把用户在"全局请求头"配的 header (Authorization / X-Tenant-Id / X-Trace-Id 等) 注入到 `executor.g_headers`, 所有 HTTP 请求都会带。

`run_interface_by_task` 漏调 → 任务执行时 `executor.g_headers` 永远 `[]` → 全部 HTTP 请求丢全局 header → API 网关 401 / 业务对账不上 (X-Tenant-Id 缺失漏数)。

### 2.2 后果

- 任务级执行跟单接口/组/业务流 3 个入口行为不一致。
- 用户配了"全局 header"后, 单接口调试 OK, 一上任务就挂, 排查时定位很慢 (因为同一个用例业务流跑 OK, 任务跑就 401)。

### 2.3 修法

`croe/interface/runner.py:308-315` (在 `run_interface_by_task` 函数体开头) 加:
```python
# BUG-RB2 修复: 跟另外 3 个入口 (try_interface / try_group / run_interface_case)
# 对齐, 调 init_global_headers 把全局 header 注入到 executor.g_headers。
await self.init_global_headers()
for attempt in range(retry + 1):
    result = await self.interface_executor.execute(...)
    ...
```

### 2.4 为什么不改方案 B (init_global_headers 改成 classmethod / 不依赖 self)

`init_global_headers` 操作 `self.executor.g_headers`, 必须有 self; 改 classmethod 会让它不依赖具体 runner 实例, 但实际全局 header 注入到 `executor` 后还是只影响当前 runner 自己的 executor, 语义没变。**保留 self 调法最直接, 4 个入口对齐**。

### 2.5 锁住测试

- `test_bug_rb2_run_interface_by_task_calls_init_global_headers`: 锁 `await self.init_global_headers()` 必须在 `for attempt in range` 循环之前。
- `test_bug_rb2_all_four_entries_init_global_headers`: 锁 4 个入口 (try_interface / try_group / run_interface_case / run_interface_by_task) 全部调 `init_global_headers`, 行为一致。

## 3. BUG-DOC 详情

### 3.1 根因

`app/mapper/interfaceApi/interfaceResultMapper.py:recompute_case_result_nums` 旧代码:
```python
if session is None:
    raise ValueError("recompute_case_result_nums requires an external session ...")
# ... 用 session 执行 SELECT, 然后调 cls.update_by_id(..., session=session)
```

但 `result_writer.py:367` (E8/E9 修复时写) 注释:
```python
# recompute_case_result_nums 自管事务, finalize 末尾调一次兜底
```

`result_writer` 的 `finalize_case_result` 包了 `try/except` 静默吃异常:
```python
try:
    await InterfaceCaseResultMapper.recompute_case_result_nums(case_result_id=case_result_id)
except Exception as e:
    log.error(f"recompute_case_result_nums error: {e}")
    # 不会 raise, 业务对账失败被吞
```

### 3.2 后果

- 接口行为跟 docstring 写的不一样: 注释说"自管事务", 实际**强制要求 caller 传 session**。
- 调用方 `result_writer.finalize_case_result` 是无 session 的 finalize 场景 (在 executor.flush 末尾, 业务上 finalize 一次即可), 走到这里直接 raise, 静默 except 后业务流 total/success/fail 永远停留在初值, 对账不工作。

### 3.3 修法

`app/mapper/interfaceApi/interfaceResultMapper.py:85-156` 改成:
```python
async def recompute_case_result_nums(
    cls,
    case_result_id: int,
    session: Optional[AsyncSession] = None,
) -> Dict[str, int]:
    """...
    Args:
        case_result_id: 用例结果 ID
        session: 外部传入的 session (事务复用, D4 哲学)。None 时本方法自管
            事务 (开自己的 cls.transaction() 跑完 commit/rollback)。
    """
    async def _do_query(sess: AsyncSession) -> Dict[str, int]:
        stmt = select(
            func.count(InterfaceResult.id).label("total"),
            func.sum(case((InterfaceResult.result == True, 1), else_=0)).label("success"),
            func.sum(case((InterfaceResult.result == False, 1), else_=0)).label("fail"),
        ).where(InterfaceResult.case_result_id == case_result_id)
        row = (await sess.execute(stmt)).one()
        total = row.total or 0
        success = row.success or 0
        fail = row.fail or 0
        await cls.update_by_id(
            id=case_result_id,
            total_num=total, success_num=success, fail_num=fail,
            session=sess,
        )
        return {"total": total, "success": success, "fail": fail}

    try:
        if session is None:
            async with cls.transaction() as session:
                return await _do_query(session)
        return await _do_query(session)
    except Exception as e:
        log.error(f"recompute_case_result_nums error: {e}")
        raise
```

### 3.4 为什么不改方案 B (只删 raise, 不开新事务)

只删 raise 让 `sess.execute(...)` 在没有 session 的情况下炸 `NameError` 之类。必须开自己的 `cls.transaction()`, 否则 SQLAlchemy 2.0 async 模式下 `AsyncSession` 不能凭空创建。

### 3.5 锁住测试

- `test_bug_doc_recompute_session_none_no_longer_raises`: 用 `inspect.getsource` 锁源码, 不调 DB, 验证:
  1. 没有 `raise ValueError("...external session...")`
  2. 有 `if session is None` 分支
  3. 有 `cls.transaction()` 自管事务
- `test_bug_doc_recompute_with_external_session_uses_it`: async 测试, mock AsyncSession + row + execute().one(), 验证外部 session 传进来时 `update_by_id` 复用同一 session (D4 风格)。
- 旧测试 `test_bug_e8_e9_recompute_requires_external_session` (E8/E9 修时写的, 验 session=None raise) 改名为 `test_bug_e8_e9_recompute_session_none_no_longer_raises`, 改用 inspect 锁源码 (新行为: 不 raise, 走自管事务)。

## 4. 周边影响

### 4.1 4 个执行入口对齐 (RB2)

| 入口 | 文件:行 | 调 `init_global_headers` | 行为 |
|---|---|---|---|
| `try_interface` | runner.py:78 | ✅ | 修前 OK |
| `try_group` | runner.py:103 | ✅ | 修前 OK |
| `run_interface_case` | runner.py:169 | ✅ | 修前 OK |
| `run_interface_by_task` | runner.py:315 | ✅ **新加** | 修前漏, 任务执行丢全局 header |

### 4.2 recompute 不再 raise (DOC)

| 调用方 | session | 修前 | 修后 |
|---|---|---|---|
| `result_writer.finalize_case_result` (末尾兜底) | None | raise ValueError → 静默 except 丢对账 | 自管事务, 对账成功 |
| 业务流 `run_interface_case` 末尾主动调 | 传进来 (复用) | OK | 仍然 OK, 复用同 session |
| 单接口 `try_interface` 不调 | — | N/A | N/A |

### 4.3 status 统一 enum (M9-2)

| 写点 | 修前 | 修后 |
|---|---|---|
| `result_writer.write_step_result` (parent step flush 路径) | `"SUCCESS"/"FAIL"` str | `StepStatusEnum.SUCCESS/.FAIL` enum |
| 8 个 `step_content_*.py` (M9 已修) | enum | enum |

status 列改 `Enum(StepStatusEnum, native_enum=False, length=20)` 时, result_writer 路径不再炸 `LookupError`。

## 5. 测试覆盖

| 文件 | 测试 | 类型 |
|---|---|---|
| `tests/croe/interface/test_bug_m9_2_rb2_doc_batch.py` | 6 个 (本批新增) | 静态源码锁 + 1 个 async mock |
| `tests/croe/interface/test_bug_e8_e9_recompute_case_result_nums.py` | 1 个 (本批改写, E8/E9 旧测试改名 + 改 assert) | 静态源码锁 |
| `tests/croe/interface/_bug_ids.py` | 3 个常量 (本批追加) | M9-2 / RB2 / DOC |

**全量回归**: 392 (基线) + 6 (新) - 1 (E8/E9 旧测试改写, 1→1) = 397 unit + 1 skipped + 3 deselected = 398 passed, 0 fail。

## 6. 不在本批范围 (留给下批)

- **D4-V2 partial commit**: `interfaceResultMapper.py:229-238` + `349-355` 两处显式 `await session.commit()`, 让 bulk_insert 隐式 commit 的事务边界被破坏, FK 已回填但主表空。修法: 删 `await session.commit()`, 让外层 `cls.transaction()` 统一管。
- 5 个 P1: 魔法数字 200, init_global_headers cache, 错属性名, 错误日志 redaction, kwargs["id"] code smell。

## 7. 关键约定 (沿用)

- 测试不加 DB, 用 `inspect.getsource()` + 正则 + mock 锁产品代码
- BUG_ID 必加 `_bug_ids.py`, commit msg + 测试 + 报告三处引用
- 修复注释格式: `# BUG-{ID} 修复: 一句话根因 + 一句话修法 + 为什么不修方案 B`
- 测试文件命名: `test_bug_{id1}_{id2}_{id3}_batch.py` (一锅端)
- commit msg 格式: `fix({IDs}): N 个 P0 一锅端\n\n[BUG-{ID}] ...\n...\n\n测试:...\n回归:...\n报告:...`
