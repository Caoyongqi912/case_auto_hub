"""
V2 审查报告中的 BUG 编号常量。

目的:让回归测试和审查报告交叉引用,任何一个回归测试都能直接对应到 V2 报告的某个 BUG 编号。
"""

# 模型层
BUG_M1 = "M1"  # target_id ClassVar
BUG_M2 = "M2"  # case_title 长度
BUG_M3 = "M3"  # BaseModel JTI

# 流程层
BUG_F1 = "F1"  # interfaceLog 字段名
BUG_F2 = "F2"  # 早返 None
BUG_F3 = "F3"  # init_global_headers 错位
BUG_F4 = "F4"  # init_interface_case_vars 静默
BUG_F5 = "F5"  # error_stop 状态机

# Mapper 层
BUG_D1 = "D1"  # result_writer 单例

# 执行器
BUG_E1 = "E1"  # HttpxClient 资源

# 安全
BUG_S1 = "S1"  # getattr 沙箱逃逸
BUG_S2 = "S2"  # import 沙箱逃逸
BUG_S3 = "S3"  # SCRIPT_TIMEOUT 未生效

# 变量
BUG_V1 = "V1"  # name mangling

# M11 后续追加
BUG_M11 = "M11"  # *_uid 长度截断

# V4 审查 + D2 追加
BUG_V4 = "V4"  # _hub_api_request 同步 httpx.Client 阻塞
BUG_D2 = "D2"  # bulk_insert_results 异常吞掉部分成功记录

# D4 追加
BUG_D4 = "D4"  # bulk_insert_* 隐式 commit, 多表批量不在同事务
BUG_M5 = "M5"  # polymorphic_on 用 enum int, 重排炸库

# F8 追加: 模块单例 result_writer 死灰复燃, STEP_API content_result 永远不落盘
BUG_F8 = "F8"  # result_writer 注入 ExecutionContext, 替代模块单例
