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


# V2: list2dict 重复 key 静默覆盖
# 步骤 1 提取 token=abc, 步骤 2 又提 token=xyz (配置错误/数据脏),
# 后者静默覆盖前者, 业务上不知道哪个步骤改了哪个值。
# 保持 last-wins 语义 (跟 dict.update 一致), 但 WARNING 出去。
BUG_V2 = "V2"  # list2dict 重复 key WARNING


# D5: query_steps 多 joinedload 笛卡尔积

# D8: APILoopContentStrategy._update_loop_result 函数体用 step_context.result_writer
# 但函数签名漏收 step_context 参数, 4 个调用点都漏传, 一进去就 NameError
# 整 case 跑挂, 日志被清空。修: 签名加 step_context: CaseStepContext,
# 4 个调用点都加 step_context=step_context。
BUG_D8 = "D8"

# S4: hub_request 缺 SSRF 防御
# _hub_api_request 在用户脚本沙箱以 hub_request 名义暴露, 攻击者可写
# hub_request("http://169.254.169.254/...") 偷云元数据 / 打内网 /
# hub_request("file:///etc/passwd") 读本地文件。
# 修: scheme 白名单 http/https + DNS 解析后 IP 黑名单
# (loopback / private / link-local / reserved / multicast) +
# HUB_REQUEST_ALLOW_PRIVATE=1 逃生口。
BUG_S4 = "S4"

# V6: 引用未定义变量时静默返回变量名
# _resolve_vars / get_var 缺失变量时返变量名字符串, URL 变成
# /users/user_id/ 静默错, 操作员误以为是 API 挂。
# 修: WARNING 兜底 + VARIABLE_TRANS_STRICT=1 严格模式抛 KeyError。
BUG_V6 = "V6"

# E8 + E9 合修: case_result total/success/fail 兜底
# E8: total_num init 时设一次 = case_api_num, 之后从不更新
# E9: GROUP/LOOP/CONDITION 等 parent step case_result.success_num += 1
#     跟实际 API 数不对称 (group 跑 5 个 API 只 +1)
# 修: finalize_case_result 末尾用 interface_result 表 COUNT 覆写一次,
#     step strategy 的手动维护保留 (不动在线行为), recompute 兜底对账。
BUG_E8 = "E8"
BUG_E9 = "E9"





# D7: query_steps_result 漏 LoopStepContentResult.interface_results 的 joinedload
# M6-hotfix 修 detached instance 时只补了 API/Group/Condition 三个 parent subtype,
# 漏了 LoopStepContentResult.interface_results。前端拿循环步骤 to_dict() 时触发
# self.interface_results lazy-load, session 已关 → 静默返回 [], data 永远空。
# 修: joinedload 列表里补上 poly.LoopStepContentResult.interface_results。
BUG_D7 = "D7"

# 5 个 joinedload(APIStepContent.interface_api 等) 是死代码,
# 5 个 step strategy 都用 step_content.target_id + Mapper.get_by_id
# 自行 fetch, 不会用 ORM relationship 预加载。
# 旧 .options(joinedload(...)) 让 SQL 多 5 个 LEFT JOIN, 5x 行宽膨胀, 0 收益。
BUG_D5 = "D5"  # query_steps 删除 5 个死 joinedload
