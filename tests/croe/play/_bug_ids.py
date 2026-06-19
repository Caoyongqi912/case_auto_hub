"""
UI 自动化 (croe/play + app/mapper/play + app/model/playUI) BUG 编号常量。

目的:让回归测试和审查报告交叉引用, 任何一个回归测试都能直接对应到某个 BUG 编号。
"""

# P-R1 修复: play_runner.py:execute_case 之前 except 块 raise 抛回去,
# 任务级 retry 看不到 case_success=False, 整个 task 直接挂, 进度
# (success_number/fail_number) 不准。修: except 块只设 case_success=False,
# 不 raise; finally 仍写结果, 调用方 retry 正常。
BUG_P_R1 = "P-R1"

# P-R2 修复: task_runner.py:execute_task 之前 query_case 调了 2 次
# (L36-37 被 L46-48 覆盖), 多 1 次 DB + 两次结果可能因并发修改不同。
# 修: 删第一次 query, 保留第二次。
BUG_P_R2 = "P-R2"

# P-R3 修复: task_runner.py:__execute_case 之前 init_case_variables 在
# retry loop 内, 每次 retry 都从 DB 拉同样的 case vars (多 1 次 DB/retry)。
# 修: 提到 retry loop 外, 每个 case 跑前一次性 init。
BUG_P_R3 = "P-R3"

# P-R4 修复: task_runner.py:__execute_case 之前 error_continue 写死 False,
# 即便调用方想让失败继续, 也无法设置。修: 加 error_continue 到
# PlayTaskExecuteParams, 透传给 execute_case。
BUG_P_R4 = "P-R4"

# P-R5 修复: _base.py:write_result 之前 `if not result.success and not ignore`
# 过滤掉 ignore=True 时的失败信息, 排查 ignored 步骤为什么失败无线索。
# 修: 失败就写错误信息到 case_result (不管 ignore), 但 ignore 步骤不会
# 让 case 失败 (step_strategy 里 success=True 返给 runner)。
BUG_P_R5 = "P-R5"

# ---------------------------------------------------------------------------
# P1 批: 高 ROI 修复
# ---------------------------------------------------------------------------

# P-1-1 修复: app/mapper/play/*.py 32 处 `except Exception as e: ...; raise e`
# 吞 traceback。修: 全部改 `raise` (bare re-raise, 保留 traceback); 4 处
# `log.error(e)` 改 `log.exception(...)` 把 traceback 也写进日志。
BUG_P_1_1 = "P-1-1"

# P-1-2 修复: app/model/playUI/playCase.py:PlayCaseResult.ui_case_Id 大写 I
# 错属性名, Python 习惯 snake_case。修: 加 ui_case_id property (read+write)
# 兼容到 ui_case_Id 字段, 1-2 release 过渡; mapper 和 schema 改用 ui_case_id
# (schema 用 alias 兼容 ui_case_Id 客户端入参)。
BUG_P_1_2 = "P-1-2"

# P-1-3 修复: app/model/playUI/playTask.py:PlayTaskResult.rate_number 之前
# Column(INTEGER) 但 writer.py 用 round(..., 2) 写 float, MySQL 静默截断
# 85.5% 变成 85% (丢 1 位小数)。修: 改 Column(Float) 保留小数, 已有部署
# 需手动跑迁移 ALTER TABLE。
BUG_P_1_3 = "P-1-3"

# P-1-4 修复: croe/play/writer.py:PlayCaseResultWriter.write_result 之前参数
# 名 SUCCESS (大写) 违反 PEP 8, 跟 result.success 风格不一致。修: 改
# success (snake_case), 内部用 success 变量替换 SUCCESS。
BUG_P_1_4 = "P-1-4"

# P-1-5 修复: croe/play/writer.py:ContentResultWriter.__repr__ 末尾双
# `> />` (拼写错误), repr 输出 `<...> ... />`。修: 改单 `/>` 收尾。
BUG_P_1_5 = "P-1-5"

# P-1-6 修复: croe/play/writer.py:ContentResultWriter.update_content_result
# 之前只更新 content_result 字段, use_time 是占位时的初值 (几乎为 0)。
# 修: 重算 use_time = now - start_time, 让步骤组耗时反映真实执行时间。
BUG_P_1_6 = "P-1-6"

# P-1-7 修复: croe/play/play_runner.py:__clean / __init_page 双下划线
# 触发 Python name mangling, 子类化 / mock 拿不到。修: 改 _clean / _init_page
# (单下划线, 仍是 private 语义, 但不被 mangling)。
BUG_P_1_7 = "P-1-7"

# P-1-8 修复: croe/play/play_runner.py:init_case_variables 之前失败 raise e,
# 跟 error_continue 语义冲突 (error_continue=True 仍被 raise 中断)。修:
# 失败只 log.exception + starter.send WARNING, 不 raise, 让 case 继续跑。
BUG_P_1_8 = "P-1-8"

# ---------------------------------------------------------------------------
# P2 批: 中优先级修复
# ---------------------------------------------------------------------------

# P-2-1 修复: app/mapper/play/playCaseMapper.py:association_groups 和
# copy_content 函数体内有 `from app.mapper.play.playStepGroupMapper import
# PlayStepGroupMapper` 内联 import, 应该放文件顶部。修: 移到顶部, 删
# 内联 import (静态分析 + 避免 lazy import 的循环依赖风险)。
BUG_P_2_1 = "P-2-1"

# P-2-2 修复: app/mapper/play/playCaseMapper.py:reload_content 死代码, 全仓
# grep 无任何 caller。修: 加 deprecation docstring, 不删 (接口稳定, controller
# 没暴露, 之后批量刷新步骤名称/描述时还能用, 留着无害)。
BUG_P_2_2 = "P-2-2"

# P-2-3 修复: croe/play/play_runner.py:execute_case 之前没有 trace_id, 多
# case 并发时日志无法定位"这条日志是哪条 case 跑的"。接口自动化已经有
# OBS-2 trace_id, UI 一直缺。修: execute_case 进入时 set_trace_id (8 字符
# 够区分并发), finally 块 clear_trace_id 防泄漏。复用了 interface 已有
# ContextVar, 不引入新机制。
BUG_P_2_3 = "P-2-3"

# ---------------------------------------------------------------------------
# P3 批: 边角修复 (re-review 阶段)
# ---------------------------------------------------------------------------

# P-3-1 修复: croe/play/task_runner.py:execute_task 之前 init_result 抛
# 异常时整 execute_task 直接挂, task_result 没初始化, task 永远显示
# RUNNING (孤儿任务), 用户看不到任务结束。修: init_result 包 try, 失败
# 时 log.exception + return, 让 caller 拿不到结果但不挂。
BUG_P_3_1 = "P-3-1"
