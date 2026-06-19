# UI 自动化 (croe/play + app/mapper/play + app/model/playUI) 深度 review

**review 时间**: 2026-06-21
**基础 commit**: 499ca47
**review 范围**: 30 个 croe/play/ 文件 + 7 个 mapper + 9 个 model + 6 个 controller
**触发**: 用户 "对core 中的UI自动化代码进行审核...包含model层、mapper层、核心逻辑层"

## 0. TL;DR - 发现 5 个 P0 + 8 个 P1 + 测试覆盖 = 0

| 严重度 | 编号 | 文件:行 | 现象 | 修法 |
|---|---|---|---|---|
| **P0** | **P-R1** | `croe/play/play_runner.py:execute_case` (except + raise) | `except` 块 `raise` 抛回去, 任务级 retry 失效 (task_runner 看不到 case_success=False, 整个 task 直接挂) | `except` 块只设 `case_success=False`, 不 raise; finally 仍写入结果 |
| **P0** | **P-R2** | `croe/play/task_runner.py:execute_task` (L36-37 + L46-48) | 同一 `play_cases = await PlayTaskMapper.query_case(taskId=task.id)` 调了 2 次, 第一次结果被覆盖, 多 1 次 DB 查询 | 删第一次 query, 保留第二次 |
| **P0** | **P-R3** | `croe/play/task_runner.py:__execute_case` (retry loop) | 每次 retry 都调 `init_case_variables` (从 DB 拉 case vars), retry 之间无清理, 变量累积, 业务变量被前一次失败污染 | retry 间隔不清 vm, 仅 add `params.variables`; 或加 clear between retries |
| **P0** | **P-R4** | `croe/play/task_runner.py:__execute_case` | `error_continue` 参数有定义但从不传给 `execute_case(error_continue=...)`, 写死 False, 重试用例无法 error_continue | 透传 `error_continue` 参数 |
| **P0** | **P-R5** | `croe/play/executor/step_content_strategy/_base.py:write_result` | `if not result.success and not ignore: set_error_step_info` — 步骤 ignored=True 时, 失败信息 (msg/screenshot) 全部丢失, 排查 ignored 步骤失败原因无线索 | ignore 时也写截图/msg 到 result, 但不标 case 失败 |
| P1 | 1 | `app/mapper/play/*.py` 散落 5+ 处 | `try/except Exception as e: raise e` — 丢 traceback, 应该 `raise` (无 e) 或干脆不 try | 统一删 try/except, 用 `raise` |
| P1 | 2 | `app/model/playUI/playCase.py` | `PlayCaseResult.ui_case_Id` 大写 I 错属性名, Python 习惯 snake_case (跟 `task_result_id` 一致) | 改 `ui_case_id`, 加 property 兼容 `ui_case_Id` (1-2 release 过渡) |
| P1 | 3 | `app/model/playUI/playTask.py:PlayTaskResult` | `rate_number = Column(INTEGER, ...)` 但赋值 `round(success/total*100, 2)` 是 float, 静默写错 / 截断 | 改 `Column(Float)` 或赋值时 `int()` |
| P1 | 4 | `croe/play/writer.py:PlayCaseResultWriter.write_result(SUCCESS: bool)` | 大写 `SUCCESS` 参数名违反 PEP 8, 跟 `result.success` 风格不一致 | 改 `success: bool` |
| P1 | 5 | `croe/play/writer.py:ContentResultWriter.__repr__` | 末尾双 `> />` 多余 | 删 |
| P1 | 6 | `croe/play/writer.py:ContentResultWriter.update_content_result` | 只更新 `content_result` 字段, 不更新 message/use_time/截图, 跟 `add_content_result` 风格不一致 | 改成全字段更新 (rebuild) 或干脆不暴露 (内部用) |
| P1 | 7 | `croe/play/play_runner.py:__clean / __init_page` | 双下划线 private name mangling, 实际不是要 mangling (只防子类覆盖), 单下划线更直白 | 改 `_clean / _init_page` |
| P1 | 8 | `croe/play/play_runner.py:init_case_variables` | 调 `add_vars` 失败时 raise, 但单步失败时整个 case 应该继续 (error_continue 才有意义) | 失败时 WARNING, 不 raise |

**测试覆盖**: 0 个 play 单元测试 (tests/croe/play/ 不存在)。本次 5 个 P0 + 8 个 P1 一锅端时同步加 12+ 单元测试。

## 1. 4 入口 + 3 层 结构

### 1.1 入口 (类比接口自动化的 4 入口)

| 入口 | 文件 | 状态 |
|---|---|---|
| `PlayRunner.run_case` | play_runner.py | 业务流单跑 (UI 调试入口) |
| `PlayTaskRunner.execute_task` | task_runner.py | 任务执行 (带 retry + 多 case) |
| `PlayRunner.execute_case` | play_runner.py | 单 case 内部循环 (被 run_case + task_runner 共用) |

只有 2 个入口, 比接口自动化的 4 个少。但 retry / cleanup / 错误传播模式应一致。

### 1.2 三层

| 层 | 文件数 | 关键问题 |
|---|---|---|
| Model | 9 文件 | `ui_case_Id` 错属性名, `rate_number` 类型, 大量 `nullable=True` 缺省 |
| Mapper | 7 文件 | `raise e` 丢 traceback 5+ 处, 部分方法 `except` 后 `raise e` 而不是 `raise` |
| 核心逻辑 | 30 文件 (croe/play) | retry 失效 (P-R1), 重复查询 (P-R2), 变量累积 (P-R3), error_continue 不传 (P-R4), 失败信息丢失 (P-R5) |

## 2. P0 详情

### 2.1 P-R1: `execute_case` except + raise 破坏 retry

**文件**: `croe/play/play_runner.py:execute_case` (~line 110)

**当前代码**:
```python
try:
    page_manager = await self.__init_page()
    ...
    for index, step_content in enumerate(...):
        ...
except Exception as e:
    log.exception(e)
    case_success = False  # 发生异常时标记为失败
    raise  # 关键: 抛回去
finally:
    ...
    if case_success or write_result_on_failure:
        await content_writer.flush()
        await case_result_writer.write_result(case_success)
    await self.starter.over(case_result_writer.play_case_result.id)
    await self.__clean(page_manager)
```

**调用方 task_runner.py:__execute_case**:
```python
case_success = await play_runner.execute_case(
    play_case=play_case,
    ...
    write_result_on_failure=is_last_attempt
)
if case_success:
    task_result.success_number += 1
    break
if not is_last_attempt:
    ...
    continue
else:
    task_result.fail_number += 1
```

**后果**:
- `execute_case` 内部 except 抛回去 → 整个 task_runner.__execute_case 的 for 循环炸
- `task_result.success_number += 1` / `fail_number += 1` 都不跑
- retry 失效: 第 1 次失败 → 整个 task 异常, 没 retry
- 任务进度 `success_number/fail_number` 不准确

**修法**: `except` 块只设 `case_success = False`, **不 raise**。finally 块照常写结果。调用方拿到 `case_success=False`, retry 逻辑正常工作。

**为什么不改方案 B (finally 写结果 + caller 异常处理)**: 接口自动化的 `run_interface_case` 也是 except 后只 log, finally 写, 不 raise。风格统一。

### 2.2 P-R2: `execute_task` 重复查询

**文件**: `croe/play/task_runner.py:execute_task` (L36-37, L46-48)

**当前代码**:
```python
async def execute_task(self, params):
    if isinstance(params.task_id, int):
        task = await PlayTaskMapper.get_by_id(...)
    else:
        task = await PlayTaskMapper.get_by_uid(...)
    
    play_cases = await PlayTaskMapper.query_case(taskId=task.id)  # 第 1 次
    if not play_cases:
        ...
        return
    
    ...
    play_cases = await PlayTaskMapper.query_case(taskId=task.id)  # 第 2 次 (覆盖第 1 次)
    if not play_cases:
        ...
        return
```

**后果**: 多 1 次 DB 查询 (浪费), 第一次结果被覆盖 (如果中间有并发修改, 两次结果可能不同, 数据竞争)。

**修法**: 删第一次 query, 保留第二次 (跟 None-check 一起)。或者两次都保留, 第一次当 sanity check 提前返回 (但成本高)。建议: 删第一次, 第二次在 `if not play_cases` 之后用。

### 2.3 P-R3: retry 变量累积

**文件**: `croe/play/task_runner.py:__execute_case` (L90-110)

**当前代码**:
```python
for play_case in play_cases:
    for r in range(params.retry + 1):
        play_runner = PlayRunner(starter=self.starter)
        if params.variables:
            await self.starter.send(f"添加变量 {params.variables}")
            await play_runner.variable_manager.add_vars(params.variables)
        
        await play_runner.init_case_variables(play_case=play_case)  # 每次 retry 都拉 DB
        case_result_writer = PlayCaseResultWriter(...)
        ...
        case_success = await play_runner.execute_case(...)
```

**后果**:
- 每次 retry 都新建 `PlayRunner` (有自有 `VariableManager`), 所以 `__clean` 会 `vm.clear()`, 不会真的累积到下一次
- 但 `play_case` vars 每次 retry 都从 DB 重新拉 + add_vars 到新 vm, 没问题
- **实际问题**: 每次 retry `init_case_variables` 都从 DB 拉同样的 vars, 没缓存, 多 1 次 DB/retry

**修法**: 在 retry loop 外一次性 `init_case_variables` + `add_vars(params.variables)`, retry 内部不清 vm (因为每次新建 runner, vm 总是新)。或者 retry loop 内部用同一个 runner, retry 前 `vm.clear()`。当前架构用前者更简单。

### 2.4 P-R4: `error_continue` 不透传

**文件**: `croe/play/task_runner.py:__execute_case`

**当前代码**:
```python
async def __execute_case(self, params, play_cases, task_result):
    """执行用例"""
    for play_case in play_cases:
        for r in range(params.retry + 1):
            ...
            case_success = await play_runner.execute_case(
                play_case=play_case,
                task_result=task_result,
                error_continue=False,  # 写死 False
                ...
            )
```

**后果**:
- `PlayTaskExecuteParams` 没有 `error_continue` 字段
- 即便调用方想让失败继续, 也无法设置
- 跟 `run_case` 的 `error_continue: bool = False` 参数不一致

**修法**: 在 `PlayTaskExecuteParams` 加 `error_continue: bool = False` 字段, 透传给 `execute_case(error_continue=params.error_continue)`。

### 2.5 P-R5: ignore 步骤的失败信息丢失

**文件**: `croe/play/executor/step_content_strategy/_base.py:write_result` (L40-50)

**当前代码**:
```python
async def write_result(self, result, start_time, step_context, ignore=False):
    content_result = await self._build_content_result(...)
    await step_context.play_step_result_writer.add_content_result(...)
    
    # 失败信息 写入 case result
    if not result.success and not ignore:
        await step_context.play_case_result_writer.set_error_step_info(content_result)
```

**后果**:
- `ignore=True` 步骤失败时, 截图 + 失败信息 (`content_message` / `content_screenshot_path`) 都写到了 content_result 里 (via `_build_content_result` 截图)
- **但是** `set_error_step_info` 不调, 也就是说 `PlayCaseResult.ui_case_err_step` / `ui_case_err_step_msg` 等字段不被设置
- 排查 ignored 步骤为什么失败: 前端只能看 step content 列表, 不能直接定位 "ignored 步骤 X 失败"

**修法**: `if not result.success` (不管 ignore) 时都调 `set_error_step_info` (写截图和 message), 但不标 case 失败 (因为 ignore 之后 success=True)。这样 ignored 步骤的失败信息仍可查。

## 3. P1 详情 (8 个)

### 3.1 P1-1: `raise e` 丢 traceback 5+ 处

**文件**: `app/mapper/play/playCaseMapper.py` (5+ 处), `app/mapper/play/playResultMapper.py` (1 处), `app/mapper/play/playTaskMapper.py` (3+ 处)

**当前模式**:
```python
try:
    async with cls.transaction() as session:
        ...
except Exception as e:
    log.error(e)
    raise e  # 丢 traceback, 跟 log.error 重复
```

**修法**:
- 删 `try/except` (无意义包装, 让异常自然传播)
- 或者改 `raise` (无 e, 保留 traceback)

**为什么不改方案 B (每处加具体异常类型)**: 接口自动化已经在用 `log.exception(e)` 模式, UI 应该对齐。

### 3.2 P1-2: `ui_case_Id` 错属性名

**文件**: `app/model/playUI/playCase.py`

**当前代码**:
```python
class PlayCaseResult(BaseModel):
    __tablename__ = "play_case_result"
    ui_case_Id = Column(INTEGER, ForeignKey('play_case.id', ondelete='CASCADE'), comment="所属UI用例")
```

**后果**:
- Python snake_case 习惯是 `ui_case_id`, 跟 `task_result_id` 字段一致
- 调用方: `cls.__model__.ui_case_Id` (大写 I), 跟 ORM 习惯不符
- 静态分析工具会报 naming warning

**修法**: 改 `ui_case_id` (Column 名 + 所有引用)。1 个 release 过渡期加 `ui_case_Id` property 兼容旧数据/外部调用, 然后 1-2 release 后删。

### 3.3 P1-3: `rate_number` 类型 mismatch

**文件**: `app/model/playUI/playTask.py:PlayTaskResult.rate_number`

**当前代码**:
```python
rate_number = Column(INTEGER, default=0, comment="通过率")
...
task_result.rate_number = round(task_result.success_number / task_result.total_number * 100, 2)
```

**后果**: `round(..., 2)` 返 float (e.g. 85.5), 写 INTEGER 列时 MySQL/SQLAlchemy 会强制 int(85.5) = 85, 静默丢精度。

**修法**: 改 `Column(Float)` 或者赋值时 `int(round(...))`。

### 3.4 P1-4: `write_result(SUCCESS: bool)` 大写参数

**文件**: `croe/play/writer.py:PlayCaseResultWriter.write_result`

**修法**: 改 `success: bool`, 改所有调用方。

### 3.5 P1-5: `ContentResultWriter.__repr__` 双 `> />`

**文件**: `croe/play/writer.py`

**当前**: `f"<ContentResultWriter case_result_id={self.play_case_result_id}> task_result_id={self.play_task_result_id}> results={len(self.content_results)}> />"`

**修法**: 删末尾 `> />`。

### 3.6 P1-6: `ContentResultWriter.update_content_result` 半更新

**文件**: `croe/play/writer.py:update_content_result`

**当前**: 只更新 `content_result = success` 字段。

**修法**: 删这个方法 (或重构成"全字段 rebuild"), 因为现在 `add_content_result` 一次性写, 没机会更新。如果要支持 retry, 改 `_build_content_result` 全量更新。

### 3.7 P1-7: `__clean` / `__init_page` 双下划线

**文件**: `croe/play/play_runner.py`

**修法**: 改 `_clean` / `_init_page` (单下划线)。

### 3.8 P1-8: `init_case_variables` 失败 raise 整个 case 挂

**文件**: `croe/play/play_runner.py:init_case_variables`

**当前**: 失败 `raise e` (丢 traceback), 单步失败时整个 case 跑不下去, 不符合 error_continue 语义。

**修法**: `log.exception` + `starter.send` WARNING, **不 raise**。让 case 继续 (如果 error_continue=True)。

## 4. 测试覆盖现状

| 目录 | 状态 |
|---|---|
| `tests/croe/play/` | 不存在 |
| `tests/app/mapper/play/` | 不存在 |
| `tests/app/model/playUI/` | 不存在 |

**0 个 play 单元测试**。本批修 5 P0 + 8 P1 时, 同步加 12+ 单元测试 (锁静态源码 + mock 端到端, 跟接口自动化一致)。

## 5. 不在本批范围 (留给下批)

- `playCaseMapper.py:copy_content` 对 STEP_PLAY / STEP_PLAY_GROUP 之外的 content_type 用 fallback 创建新 content 但不更新 step_num (caller 责任, 跨函数契约不清)
- `playCaseMapper.py:reload_content` 不 persist 改的 name/desc (死代码)
- `playCaseMapper.py:association_groups` 重复 `from app.mapper.play.playStepGroupMapper import PlayStepGroupMapper` (放在 try 内, 静态导入应该放顶部)
- 业务流 `execute_case` 缺 trace_id (接口自动化已有 OBS-2, UI 还没)
- 业务流 `execute_case` 缺 `result_writer` (接口自动化已有 result_writer, UI 缺, 直接走 mapper, 没法做 D4 风格事务)
- 任务级变量在 `task_runner.__execute_case` 每次 retry 都加 `params.variables`, 跟 `params.variables` 是 list 的话 add_vars 行为不一致
- 业务流 `run_case` 没有 try/finally, `init_result` 失败时 browser 不清理 (跟 `execute_case` 自己的 finally 互补, 但 run_case 缺)
- `__clean` 里 `await self.starter.clear_logs()` 不存在 (SocketSender 父类没这个方法) — 调不到会 AttributeError 但 `try/except` 静默

## 6. 关键约定 (沿用)

- 测试不加 DB, 用 `inspect.getsource()` + 正则 + mock 锁产品代码
- BUG_ID 必加 `_bug_ids.py`, commit msg + 测试 + 报告三处引用
- 修复注释格式: `# BUG-{ID} 修复: 一句话根因 + 一句话修法 + 为什么不修方案 B`
- 锁 4 入口风格统一时, 优先跟 `run_interface_case` / `run_interface_by_task` 对齐
- 业务流 retry 模式: except 块只设 success=False 不 raise, finally 写结果, caller 决定是否重试
