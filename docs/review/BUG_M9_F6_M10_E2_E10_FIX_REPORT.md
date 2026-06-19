# BUG-M9 + F6 + M10 + E2 + E10 Fix Report

**Branch**: `master`
**Commit**: (TBD)
**测试基线**: 255 → 294 unit + 1 skipped + 3 deselected (integration), 0 fail
**覆盖率**: step_content 子目录 38% → 47% (api/assert/wait 从 31/38/44% → 100%)

---

## 修复前 / 修复后 对照

| BUG | 严重度 | 修复前 | 修复后 | 测试 |
|---|---|---|---|---|
| **M10** [低] | 反作用 | `__allow_unmapped__ = True` 在 2 处, declarative class 用了反而跳过注解到 Column 的转换 | 2 处全删, mapper 正常 | 3 个 (test_bug_m10_*) |
| **F6** [中] | 截断语义 | `(index * 100) // total_steps` 整除, total=4 index=3 → 75 (int) 写 Float 字段 | `round(index / total_steps * 100, 2)` 保留 2 位小数, 跟 Float 字段对齐 | 6 个 (test_bug_f6_*) |
| **E2** [严重] | 写死 magic string | `DEFAULT_HEADERS = {"user-agent": "case_Hub_http/v0.1"}` 写死, 调用方无法覆盖 | 加 `default_user_agent` 入参, None 走 httpx 内置, 运行时 headers 仍能覆盖 | 6 个 (test_bug_e2_*) |
| **E10** [中] | 异常未兜 + 计数错 | `db_script.invoke` 裸调, 异常拖垮整个 case; `return True` + `success_num += 1` 写死, 失败 step 也算成功 | try/except + success/fail_num 正确分支 + `return success` | 3 个 (test_bug_e10_*) |
| **M9** [低] | 8 文件字面量 | 8 个 step_content 写 `status="SUCCESS"/"FAIL"` 字面量, 写错字符串不报错 | `StepStatusEnum(enum.Enum)` 统一 + model 改 `Enum(StepStatusEnum, native_enum=False, length=20)` | 6 个 (test_bug_m9_*) |

---

## 修复详情

### BUG-M10 [低] 反作用 flag

**位置**:
- `app/model/interfaceAPIModel/interfaceResultModel.py:180` (删)
- `app/model/interfaceAPIModel/contents/interfaceCaseContentsModel.py:38` (删)

**根因**: `__allow_unmapped__ = True` 是 SQLAlchemy 2.0 给 dataclass-style 基类用的开关,
declarative class 用了反而会跳过注解到 Column 的转换 (本项目全是 declarative, 0 个 dataclass)。

**修法**: 两处直接删除。`__mapper__` 仍正常工作, 字段映射不变。

**测试**:
- `test_bug_m10_no_allow_unmapped_in_result_model` - 源码 0 处
- `test_bug_m10_no_allow_unmapped_in_contents_model` - 源码 0 处
- `test_bug_m10_models_still_register_normally` - mapper 正常, 关键列存在

### BUG-F6 [中] progress 截断语义

**位置**: `croe/interface/runner.py:213, 234`

**根因**: `(index * 100) // total_steps` 是整除, 写 Float 字段会让用户读
`75.0` 误以为是 75%; 跟 round 语义不一致。

**修法**: 改 `round(index / total_steps * 100, 2)`, 注释说明语义
"已完成 N 步, progress = N/total*100, 保留 2 位小数"。

| 场景 | 修复前 | 修复后 |
|---|---|---|
| 4 步 case, 全部完成 | `100` (int) | `100.0` |
| 4 步 case, 失败停第 2 步 | `50` (int) | `50.0` |
| 4 步 case, 失败停第 3 步 | `75` (int) | `75.0` |
| 3 步 case, 失败停第 1 步 | `33` (int, 截断) | `33.33` (round) |

**测试**: 6 个, 含源码 + 4 个行为路径。

### BUG-E2 [严重] HttpxClient 写死 user-agent

**位置**: `common/httpxClient.py:19`

**根因**: `DEFAULT_HEADERS = {"user-agent": "case_Hub_http/v0.1"}` 写死, magic string
没有来源说明, 调`方无法在 `Interface.interface_headers` 里覆盖 (因为 client headers
在 client 创建时硬塞)。

**修法**:
- 删 `DEFAULT_HEADERS` class attr
- 加 `default_user_agent: Optional[str] = None` 入参
- 不传 → 走 httpx 内置 user-agent (`python-httpx/x.y.z`)
- 传了 → 注入 client headers
- 运行时 `interface_headers['User-Agent']` 仍能单次覆盖 (httpx 合并规则)

**测试**: 6 个, 含源码 0 处 magic string + 入参存在 + 4 个行为路径 (透传 / 覆盖)。

### BUG-E10 [中] step_content_db 异常处理

**位置**: `croe/interface/executor/step_content/step_content_db.py:66-105, 119-123`

**根因 (双 BUG)**:
1. `db_script.invoke` 裸调, 数据库连不上 / SQL 语法错 / 驱动异常会让 step 抛上来,
   打断整个 case loop (跟 step_content_script 的 try/except 风格不一致)
2. `return True` 写死 + `case_result.success_num += 1` 不管成功失败都 +1,
   失败 step 永远记成 success, case 计数全错

**修法**:
1. 加 try/except (跟 step_content_script 一致) + WARNING 留痕
2. 改 `if success: success_num += 1 else: fail_num += 1`
3. `return success` (修前 return True)

**测试**: 3 个, 含源码 try/except 存在 + 异常路径 (return False, status=FAIL) + 成功路径 (add_vars, status=SUCCESS)。

### BUG-M9 [低] StepStatusEnum 缺失

**位置**:
- `enums/InterfaceEnum.py` (新增 `class StepStatusEnum(enum.Enum): SUCCESS/FAIL/PENDING`)
- `app/model/interfaceAPIModel/interfaceResultModel.py:217` (`status` 改 `Enum(StepStatusEnum, native_enum=False, length=20)`)
- 8 个 step_content 文件改 `"SUCCESS"/"FAIL"` → `StepStatusEnum.SUCCESS/.FAIL`

**根因**: 8 个 step_content 文件写 `status="SUCCESS"/"FAIL"` 字面量, 没有任何 enum 约束;
写错字符串 (`"success"` / `"OK"` / `"DONE"`) 不会报错, 要等前端 / DB 查询才发现。

**修法 (跟 M5 content_type 同模式)**:
1. 加 `StepStatusEnum(enum.Enum)` 含 SUCCESS/FAIL/PENDING (PENDING 兼容旧 default)
2. model 字段改 `Enum(StepStatusEnum, native_enum=False, length=20)`, DB 存 enum NAME
3. 8 个 step_content 文件改用 enum 常量
4. assert.py / wait.py 补 `from enums import StepStatusEnum` (M9 import inject 漏了单行 from 形式)

**迁移**: `docs/MANUAL_MIGRATION.sql` 加 M9 章节 — 无需 schema DDL (native_enum=False 走 VARCHAR(20)),
仅 sanity check 脏数据 + 应用层就绪。

**测试**: 6 个, 含 enum class 存在 + 8 文件 0 处字面量 + 8 文件 import 存在 + model 是 Enum + default 是 PENDING + 拒绝错值。

---

## 覆盖率补强

| 文件 | 修复前 | 修复后 | 净增 |
|---|---|---|---|
| step_content_api.py | 31% | 100% | +69pp |
| step_content_assert.py | 38% | 100% | +62pp |
| step_content_wait.py | 44% | 100% | +56pp |
| step_content_db.py | (前批) 92% | 92% | (E10 测试纳入) |
| step_content 子目录 TOTAL | 38% | 47% | +9pp |

**新增 15 个单测** (test_step_content_{api,assert,wait}_coverage.py), mock StepBaseStrategy.interface_executor + result_writer + 各种 mapper,
覆盖了 4-5 条主路径 (interface 不存在 / 成功 / 失败 / 异常 / task_result 透传)。

---

## 后续 (留给下批)

剩 5 个文件覆盖率 < 50%:
- step_content_loop.py 18% (137 行, 复杂, 需 mock 整个 loop 状态机)
- step_content_condition.py 19% (52 行, 4 个分支)
- step_content_group.py 27% (41 行)
- step_content_script.py 30% (43 行)
- request_builder.py 43% (147 行, 大头)
- url_builder.py 44% (18 行)

预计下一批 1-1.5h 补齐, 目标 TOTAL 60%+。

---

## 验证

```bash
# 5 BUG 单元测试
.venv/bin/python -m pytest tests/croe/interface/test_bug_m9_*.py \
    tests/croe/interface/test_bug_f6_*.py \
    tests/croe/interface/test_bug_m10_*.py \
    tests/croe/interface/test_bug_e2_*.py \
    tests/croe/interface/test_bug_e10_*.py -v
# 24 passed

# 全量回归
.venv/bin/python -m pytest -m "not integration" -q
# 294 passed, 1 skipped, 3 deselected
```
