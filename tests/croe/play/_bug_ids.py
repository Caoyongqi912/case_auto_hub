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
