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
BUG_F5 = "F5"  # error_stop 状态机 (runner 强制 100, 应保留中间值)

# Mapper 层
BUG_D1 = "D1"  # result_writer 单例

# 执行器
BUG_E1 = "E1"  # HttpxClient 资源
BUG_E3 = "E3"  # TaskGroup 3.10 崩
BUG_E4 = "E4"  # _parse_url 死代码 + 跟 UrlBuilder 不一致
BUG_E5 = "E5"  # before_sql.strip() 隐式修改 ORM 字段

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

# F8-followup 追加: interface_result.content_result_id 永远 NULL (反向 FK 没回填)
BUG_F8B = "F8B"  # finalize flush 完 cache 后用 UPDATE JOIN 一次性回填

# M7: result 列 enum/bool 类型安全
# 旧 InterfaceCaseResultEnum (SUCCESS="SUCCESS", ERROR="ERROR", 同名 str 值)
# 跟 InterfaceAPIResultEnum (SUCCESS=True, ERROR=False) 同名不同值,
# 写 Boolean 列时 bool("ERROR")=True 会静默写反。已删前者, 加 helper 防御。
BUG_M7 = "M7"  # 删 InterfaceCaseResultEnum + result_writer._result_flag_to_bool

# M8: InterfaceCase.case_api_num 跟实际 step 关联数对账
# ±1/±N 散落在 5 个同步点, 移除 GROUP/CONDITION/LOOP 时 -1 写死,
# 实际一个 group 含 N 个 API, 永远算错。加 recompute_case_api_num 兜底。
BUG_M8 = "M8"  # recompute_case_api_num 兜底 5 个 ±N 同步点

# M6: with_polymorphic='*' 笛卡尔积风险
# InterfaceCaseContentResult (结果表) 用 '*' 让每次 SELECT 自动 LEFT JOIN
# 所有 8 个子类表, 行宽膨胀 8x, 网络/内存/DB 计划都浪费。
# 实际 3 个查询都只读基类字段, 删 '*' 零风险。
BUG_M6 = "M6"  # 删 InterfaceCaseContentResult 的 with_polymorphic='*'

# E6: _build_result 过度声明
# 旧签名 (Tuple[Dict, bool]) 把 success 单独返回, 但 result 字典里
# 也有 'result' 字段, 两路来源不同步风险。改返 Dict, 调用方用 result['result']。
BUG_E6 = "E6"  # _build_result 返回 Dict, 不再 (Dict, bool) tuple

# E12: extract_manager 静默吞错 + 返回 list 含失败项
# 失败时 'value' 未设, 旧实现仍把它放进返回 list, 下游日志把 value=None
# 打印出来很丑, 还要靠 list2dict 兜底 None 防御。改成只返回成功的。
BUG_E12 = "E12"  # extract_manager 只返回有 value 的 extract
