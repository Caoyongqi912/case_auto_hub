# BUG-P-1-1..P-1-8 Fix Report (UI 自动化 8 P1 一锅端)

**修复时间**: 2026-06-21
**基础 commit**: 57626f6 (P-R1..P-R5 修复后)
**触发**: `docs/review/PLAY_REVIEW_2026_06_21.md` §0 的 8 个 P1
**测试基线**: 421 pass → 修复后 439 pass, 0 fail (净增 18 个新测)
**commit**: 见本批提交

## 1. TL;DR

| ID | 文件:行 | 一句话根因 | 修法 | 状态 |
|---|---|---|---|---|
| **P-1-1** | `app/mapper/play/*.py` 32 处 | `raise e` 丢 traceback; 4 处 `log.error(e)` 不写堆栈 | `raise` (bare); `log.exception(...)` | ✅ |
| **P-1-2** | `app/model/playUI/playCase.py:PlayCaseResult` | `ui_case_Id` 大写 I 错属性名 | 加 `ui_case_id` property (read+write); mapper/schema 改 snake_case (alias 兼容) | ✅ |
| **P-1-3** | `app/model/playUI/playTask.py:PlayTaskResult` | `rate_number = Column(INTEGER)` 但 writer 写 `round(...,2)` float, MySQL 静默截断丢精度 | 改 `Column(Float)`, 已有部署需手动 ALTER | ✅ |
| **P-1-4** | `croe/play/writer.py:PlayCaseResultWriter.write_result` | 参数 `SUCCESS: bool` 大写违反 PEP 8 | 改 `success: bool` | ✅ |
| **P-1-5** | `croe/play/writer.py:ContentResultWriter.__repr__` | 末尾双 `> />` 拼写错误 | 改单 `/>` | ✅ |
| **P-1-6** | `croe/play/writer.py:ContentResultWriter.update_content_result` | 只更新 `content_result` 字段, use_time 是占位时的初值 (~0) | 重算 `use_time = now - start_time` | ✅ |
| **P-1-7** | `croe/play/play_runner.py:__clean / __init_page` | 双下划线触发 name mangling, 子类化/mock 拿不到 | 改 `_clean / _init_page` (单下划线) | ✅ |
| **P-1-8** | `croe/play/play_runner.py:init_case_variables` | 失败 `raise` 跟 `error_continue` 语义冲突 | 失败只 `log.exception` + `starter.send` warning, 不 raise | ✅ |

## 2. 详细修复

### 2.1 P-1-1 — mapper 全局 `raise e` 黑洞

**现象**: 7 个 mapper 文件共 32 处 `except Exception as e: ...; raise e` 反模式。
- `raise e` 会**重新创建异常对象并丢失原始 traceback** (Python 内部其实保留了 `__traceback__`, 但中间件 / loguru / 一些装饰器会读 `__cause__` / `__context__`, 一旦 `raise e` 触发就会拿到新的 traceback, 跟原始断点对不上)
- 4 处 `log.error(e)` 只把错误字符串写日志, 不写堆栈, 排错困难

**修法**:
1. 32 处 `raise e` → `raise` (bare re-raise, 保留原始 traceback)
2. 4 处 `log.error(e)` → `log.exception(f"... failed: {e}")` (loguru 自动带 traceback)

**为什么不统一改 except → 透传**: P-R1 修复时已经定下风格, 这次沿用: log + raise, 跟日志中间件集成。完全删 try/except 等于没有日志, 不可见。

**测试**:
- `test_bug_p_1_1_no_bare_raise_e_in_mapper[7 files]` — 参数化扫 7 个 mapper 文件, 0 处 `raise e` 残留
- `test_bug_p_1_1_log_error_e_replaced_with_log_exception` — 0 处 `log.error(e)` 残留

### 2.2 P-1-2 — `ui_case_Id` 大写 I 错属性名

**现象**: `PlayCaseResult.ui_case_Id` 大写 I 违反 Python 命名规范 (snake_case), 跟同表 `task_result_id` 风格不一致, 调用方容易写错 (`obj.ui_case_id` → `AttributeError`)。

**修法**:
1. `PlayCaseResult` 加 `ui_case_id` property (read + write), 内部读写 `self.ui_case_Id`
2. `app/mapper/play/playCaseMapper.py` 2 处 `ui_case_Id` → `ui_case_id` (用 property)
3. `app/schema/play/playCaseSchema.py:PagePlayCaseResultSchema` 字段 `ui_case_Id` → `ui_case_id` 加 `alias="ui_case_Id"`, 旧客户端传 `ui_case_Id` 仍能匹配

**为什么用 property 不用 Column rename**:
- rename Column 需 DB migration (ALTER TABLE RENAME COLUMN)
- `BaseModel._to_dict_impl` 走 `sa_inspect(...).mapper.columns` 拿 column key, 重命名也要改所有 mapper 调用
- property 是**零迁移 + 向后兼容**最稳的过渡方案, 1-2 release 后可彻底改字段名

**测试**:
- `test_bug_p_1_2_model_has_ui_case_id_property` — property + setter 存在
- `test_bug_p_1_2_mapper_uses_ui_case_id_not_ui_case_Id` — 0 处 `ui_case_Id` 残留
- `test_bug_p_1_2_schema_has_ui_case_id_alias` — schema 字段 + alias 都在

### 2.3 P-1-3 — `rate_number` Column(INTEGER) vs round() float

**现象**: `rate_number = Column(INTEGER, default=0)` 但 writer 写 `round(success/total*100, 2)`, 是 float。MySQL 接受 float 写 INTEGER 列时**静默截断** (不报错), 85.5% 变成 85% (丢 1 位小数), 通过率显示永远整数。

**修法**:
- 改 `Column(Float, default=0)`, 保留小数
- 已有部署需手动迁移: `ALTER TABLE play_task_result MODIFY COLUMN rate_number FLOAT DEFAULT 0 COMMENT '通过率';`
- (在 model 注释里写明迁移 SQL)

**为什么不选 Numeric(5,2)**: FLOAT 够用 (百分比精度 2 位小数), Numeric(5,2) 需要 SQLAlchemy 用 DECIMAL 类型序列化/反序列化, 跟现有 JSON API 的 `float` 不兼容, 多一层转换。FLOAT 在 0-100 范围 + 2 位小数的精度损失可忽略。

**测试**:
- `test_bug_p_1_3_rate_number_is_float_column` — `isinstance(col.type, Float)`

### 2.4 P-1-4 — `write_result(SUCCESS: bool)` 大写

**现象**: 参数名 `SUCCESS` (全大写) 违反 PEP 8 (应 snake_case), 跟 `result.success` 风格不一致, 调用方 IDE 不会自动补全。

**修法**: `write_result(self, success: bool)`, 内部用 `success` 变量。

**测试**:
- `test_bug_p_1_4_write_result_uses_snake_case_param` — `inspect.signature` 检查 params 列表无 `SUCCESS`, 有 `success`

### 2.5 P-1-5 — `__repr__` 双 `> />`

**现象**: `return f"... {self.play_case_result_id}> task_result_id={self.play_task_result_id}> results={...} />"` — 第一个 `>` 是闭合, 第二个是属性, 末尾 `/>` 也是闭合, 三个符号对不上。实际输出 `<... > ... />`, debug 看到一团糟。

**修法**: 改单 `/>` 收尾, 中间属性间用空格分隔。

**测试**:
- `test_bug_p_1_5_content_result_writer_repr_no_double_gt` — `> />` 子串不在 repr 源码里

### 2.6 P-1-6 — `update_content_result` use_time 黑洞

**现象**: 步骤组/条件组先 `add_content_result` 创建占位 (此时 `use_time ≈ 0`, 因为子步骤还没跑), 子步骤跑完后调 `update_content_result(step_index, success)` **只更新 `content_result` 字段, 不重算 `use_time`**, 步骤组耗时永远显示 ~0。

**修法**: `update_content_result` 内部 `end_time = now()`, `content_result.use_time = GenerateTools.timeDiff(start_time, end_time)`, 反映真实执行时间 (子步骤总和)。

**为什么不在调用方算好传过来**:
- 调用方 (group_strategy / condition_strategy) 已经在局部算 `use_time`, 但跟 `content_result.start_time` 不一定同步 (group 创建时算的 start_time, use_time 是子步骤结束后算的)
- writer 拿 `start_time` 自己重算最一致, 单一职责

**测试**:
- `test_bug_p_1_6_update_content_result_recomputes_use_time` — 源码里有 `use_time`、`timeDiff`、`start_time` 三个关键词

### 2.7 P-1-7 — `__clean / __init_page` name mangling

**现象**: 双下划线 (无尾下划线) 触发 Python name mangling: `self.__clean` 实际访问 `self._PlayRunner__clean`。后果:
- 子类化覆盖 `_clean` 不会生效 (父类 `__clean` 被 mangling)
- mock `PlayRunner.__clean` 拿不到 (因为实际是 `_PlayRunner__clean`)
- IDE 跳转混乱

**修法**: 改 `_clean / _init_page` (单下划线), 仍是 private 语义但不被 mangling。

**测试**:
- `test_bug_p_1_7_no_double_underscore_methods_in_play_runner` — `re.findall` 找非 dunder 的双下划线方法, 0 个
- `test_bug_p_1_7_clean_and_init_page_renamed_to_single_underscore` — `hasattr(_clean) + hasattr(_init_page)`

### 2.8 P-1-8 — `init_case_variables` 失败 raise 跟 error_continue 冲突

**现象**: `init_case_variables` 失败时 `raise e`, 调用方 (task_runner) 看到 Exception 走 retry 路径。即便 `error_continue=True` 也救不回来 (raise 直接挂掉整 case)。

**修法**: 失败只 `log.exception(...)` + `starter.send("⚠️ ...")` warning, 不 raise, 让 case 继续跑 (变量缺失用空值/默认值兜底)。

**为什么不变量加载失败也致命**: 变量是辅助数据 (e.g. token/host/feature flag), 单个变量加载失败不应阻塞整 case 跑。让用户在结果 warning 里看到是哪个变量没加载成功, 自己去 fix。

**测试**:
- `test_bug_p_1_8_init_case_variables_does_not_raise` — except 块无 `raise`, 有 `log.exception`

## 3. 周边影响

| 维度 | 评估 |
|---|---|
| **接口层耦合** | 无。所有 8 个修复都在 mapper/model/writer 内部, 控制器层 (`PlayController`) 不变。 |
| **数据迁移** | P-1-3 需要 `ALTER TABLE play_task_result MODIFY COLUMN rate_number FLOAT` (model 注释里有写)。其余无。 |
| **接口自动化** | 完全无影响, 本批只动 UI 侧。 |
| **回归** | 439 pass, 0 fail (414 旧 + 7 Batch 1 + 18 Batch 2) |
| **性能** | P-1-1 traceback 修复让 Sentry/loguru 完整捕获堆栈, 调试更快; 其余是行为修正, 无性能变化。 |

## 4. 文件改动清单

```
app/mapper/play/playResultMapper.py   (P-1-1: 1 raise e + 1 log.error(e))
app/mapper/play/playTaskMapper.py     (P-1-1: 10 raise e + 1 log.error(e))
app/mapper/play/playConditionMapper.py(P-1-1: 1 raise e)
app/mapper/play/playStepMapper.py     (P-1-1: 3 raise e)
app/mapper/play/playStepGroupMapper.py(P-1-1: 7 raise e)
app/mapper/play/playConfigMapper.py   (P-1-1: 2 raise e)
app/mapper/play/playCaseMapper.py     (P-1-1: 8 raise e + 2 log.error(e) + P-1-2: 2 ui_case_Id → ui_case_id)
app/mapper/play/__init__.py           (LF 换行修正)
app/model/playUI/playCase.py          (P-1-2: ui_case_id property + LF 修正)
app/model/playUI/playTask.py          (P-1-3: Column(Float) + LF 修正)
app/model/playUI/playStep.py          (LF 修正)
app/model/playUI/__init__.py          (LF 修正)
app/model/playUI/PlayConfig.py        (LF 修正)
app/model/playUI/playAssociation.py   (LF 修正)
app/schema/play/playCaseSchema.py     (P-1-2: alias 兼容)
croe/play/writer.py                   (P-1-4 + P-1-5 + P-1-6 + LF 修正)
croe/play/play_runner.py              (P-1-7 + P-1-8)
tests/croe/play/_bug_ids.py           (+ 8 个 BUG_P_1_X 常量)
tests/croe/play/test_bug_p1_1_to_p1_8_batch.py (新增, 18 测)
```

## 5. 下批 (P2 / 留给下批)

见 `docs/review/PLAY_REVIEW_2026_06_21.md` §5, 5 个遗留项:
- `playCaseMapper.py:copy_content` STEP_PLAY/STEP_PLAY_GROUP 之外 type 不更新 step_num
- `playCaseMapper.py:reload_content` 不 persist 改的 name/desc (死代码)
- 业务流 `execute_case` 缺 trace_id (接口自动化有 OBS-2)
- 业务流 `execute_case` 缺 result_writer (无法做 D4 风格事务)
- `__clean` 调 `self.starter.clear_logs()` 不存在 (AttributeError 静默)
