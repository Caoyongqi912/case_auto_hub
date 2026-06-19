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

# D6: InterfaceResult <-> APIStepContentResult 双向 FK 漂移检测 + reconcile
# InterfaceResult.content_result_id 跟 APIStepContentResult.interface_result_id
# 是同一 1:1 关系的两个方向, 任何一边漏更新就漂。F8B 只处理 'ir_missing_fk'
# (ir.content_result_id IS NULL) 这一种, 还有 'mismatch' (ir.content_result_id
# 跟 api.interface_result_id 不等) 跟 'api_missing_fk' (api 那边没记录) 两种
# 漂移没处理。修: 加 find_fk_inconsistencies (3 种 reason 全识别) +
# reconcile_fk_from_polymorphic (UPDATE JOIN 兜底覆写)。
BUG_D6 = "D6"

# OBS-1: 失败链路 trace 不可达
# 异常分支 (except) 只 log.exception, 不写 step_result、不通知用户。
# 修: 走 OBS-2 trace_id 帮定位"这条日志是哪条 case 跑的", 跨
# async/log/DB/WS 一致。失败 case 的 step_result 落盘是 InterfaceExecutor
# 单独改造 (不在本批)。
BUG_OBS_1 = "OBS-1"

# OBS-2: 缺 correlation id
# interface_case_id / case_result_id / task_result_id 在多 case 并发时, 光看
# 日志无法拼出"这条日志是哪条 case 跑的"。修: contextvars 注入 trace_id
# (8 字符 uuid hex), 跨 asyncio.Task / loguru patcher / MyLoguru 格式
# / runner 入口 + finally 清理, 一致可见。
BUG_OBS_2 = "OBS-2"

# OBS-3: 缺 log 脱敏
# URL/变量写进 log, 可能含 token / 密钥 / cookie。修: loguru patcher
# 在 emit 前 redact 敏感字段 (Authorization / Set-Cookie / Cookie /
# Password / passwd / Token / api_key / access_key / secret 等, 大小写
# 不敏感子串匹配), message 跟 extra=dict 都覆盖。
BUG_OBS_3 = "OBS-3"

# E7: extracts/asserts 默认值混乱
# _build_result 用 `ctx.extracted_vars or []` / `ctx.asserts or []`, 但子策略
# 可能传 None 进来 (Python or 链只挡 None 不挡 [None])。修复: 显式 list() 包
# 一层 + 过滤 None 项, 保证存到 DB 的总是 list[有效值]。
BUG_E7 = "E7"

# V3: ScriptManager._variables 跨脚本累积 (全局状态)
# ScriptManager.__init__ 每次都新建实例, 但 _collect_results 把变量存到
# self._variables, 同一 ScriptManager 跑多个脚本就累积。当前 interface_executor
# 每次都 ScriptManager() 新建所以不泄漏, 但语义不明, 后来人加缓存或复用就踩。
# 修: 重命名 _variables -> _script_locals, 注释里说清楚"单脚本实例跨 exec
# 不共享", 防后来误用。
BUG_V3 = "V3"

# S5: _prepare_raw_body raw text 模式多余 json.dumps
# raw_type == text 时, body 本就是字符串, 走 json.dumps 会:
#   1) 给整串加引号: "hello" -> '"hello"' (错!)
#   2) 反斜杠被 double-escape: "\\path" -> '\\\\path'
#   3) 用户已有的 JSON 字符串被 re-encode, 变量替换后意义变
# 修: body 是 str 就直接用, 不是 str 才 json.dumps。
BUG_S5 = "S5"

# S7: safe_headers 不拦截下游 interface_headers
# _prepare_headers 信任 g_headers + interface_headers, 用户可配 Host: malicious
# 等敏感 header 覆盖后端真实值。修: 加 BLOCKED_DOWNSTREAM_HEADERS 黑名单
# (Host / Content-Length / Connection / Transfer-Encoding), 拦截后 WARNING
# 不静默。
BUG_S7 = "S7"

# D9: InterfaceCaseResultMapper 2 个 pass 占位方法
# page_case_results / query_case_result 是空 `pass`, 没有任何 NotImplementedError
# 或 TODO 标记, 后续维护者分不清"忘写了"还是"故意占位"。
# 修: 改成 raise NotImplementedError + TODO 注释。
BUG_D9 = "D9"

# D10: dynamicMapper append_dynamic 时机不对
# update_interface_case / update_interface 在 update_by_id 之后调 to_dict(),
# 但 update_by_id 内部走 expunge (默认 True), 此时 lazy='selectin' 的关系
# 已不命中。当前 to_dict 只读列字段没问题, 但任何关系访问会静默拿到 stale
# data 或 detached instance 报错。修: add a `post_update_hook` callback to
# update_by_id, 让调用方在 expunge 前拿 snapshot; 或传 expunge=False 让
# 业务方自己管。
BUG_D10 = "D10"

# E11: condition_step 写库漏 assert_data
# step_content_condition 把 condition_manager 算出的 assert_data (含
# key/value/operator/condition_result) 拆成 4 个列 (condition_result /
# condition_key / condition_value / condition_operator) 写库, 漏了原始
# assert_data 字典。模型里有 assert_data JSON 列, 应一并存。修: 写库时
# 同时把 content_condition 整个 dict 存到 assert_data 列。
BUG_E11 = "E11"

# OBS-4: starter.send 的 emoji 协议
# starter.send 靠 "🫳🫳" / "✍️✍️" / "⏭️⏭️" emoji 区分步骤类型, 前端要正则
# 解析这些 emoji。一旦换前缀或加新类型, 前端要同步改, 没类型安全。
# 修: 加 STARTER_MSG_TYPE 常量, 内部走 enum 字符串前缀, 旧 emoji 保留
# 兼容 (deprecated, 仅作 fallback)。
BUG_OBS_4 = "OBS-4"

# OBS-5: set_result_field 只有 setter 没 getter / 返值语义不明
# interfaceResultMapper.py InterfaceCaseResultMapper.set_result_field 只
# add_flush_expunge, 不返回任何状态或成功标识, 调用方无法判断是否成功 (只能
# 靠 raise)。修: 改返成功 bool (True=成功, False=失败), 跟 result_writer
# 风格对齐。
BUG_OBS_5 = "OBS-5"

# OBS-6: 日志里无 case_result_id, 只有 interface_case_id
# runner.py log.info(f"查询到业务流用例  {interface_case}") 拿到 case
# 对象但不打 case_result_id, 排查时无法 grep 单个 case_result 的全链路。
# 修: 第一条 log 后追加 log.info(case_result_id=xxx), 加 trace_id 后本来
# 也能关联, 但显式 ID 更直接 (trace_id 查 map 还要多一步)。
BUG_OBS_6 = "OBS-6"

# M9: case_status String(10) 无枚举约束, step_content 8 文件写
# "SUCCESS"/"FAIL" 字面量无 enum。修: 加 StepStatusEnum, model 改
# Enum(StepStatusEnum, native_enum=False, length=20), 8 个 step_content
# 改用 enum 常量。
BUG_M9 = "M9"

# F6: progress 截断语义不一致。runner.py 在 step loop 末尾
# case_result.progress = (index * 100) // total_steps, total_steps=4
# index=3 时 75, index=4 才 100。F5 修了"不再 force 100", 但 progress
# 在 error_stop 路径是中间值而非 100%, 用户对截断语义有歧义。修:
# 加注释说明 + 用 (i+1)*100//total 一致地"完成进度"。
BUG_F6 = "F6"

# M10: __allow_unmapped__ = True 是给 dataclass-style 基类用的, 但本
# 项目全是 declarative class, 加了反而跳过注解到 Column 的转换, 是
# 反作用。修: 删 2 处 (interfaceResultModel.py:180, interfaceCaseContentsModel.py:37)。
BUG_M10 = "M10"

# E2: HttpxClient 默认 user-agent 写死 "case_Hub_http/v0.1", 调用方无法
# 在 Interface.interface_headers 里覆盖。修: 删 DEFAULT_HEADERS 写死,
# 改读运行时 headers (同 S7 黑名单模式反过来, 允许 User-Agent 覆盖)。
BUG_E2 = "E2"

# E10: step_content_db.py 调 db_script.invoke 异常时整个 step 挂, 跟
# step_content_script.py:53-77 包裹 ScriptSecurityError + Exception
# 的风格不一致。修: step_content_db 加 try/except, 失败 WARNING +
# success=False 返。
BUG_E10 = "E10"

# N2: InterfaceCaseResultMapper.page_case_results / query_case_result 是
# dead code (raise NotImplementedError, 无 caller)。原 D9 修复时改成
# raise NotImplementedError + TODO 注释, 防静默返回 None, 但本质是 dead
# code 一直在 mock 里。修: 删 2 个方法 + 加测试锁住 0 caller (防止别人
# 误加调用, 然后踩 NotImplementedError)。
BUG_N2 = "N2"

# RB1: RequestBuilder._prepare_auth KV Auth target 字段非 "query"/"header" 时
# 静默不报错。用户配错 (target="body"/"cookie" 等) 完全无线索, 调
# 试半天才发现认证字段没生效。修: 加 else 分支, log.warning 含 target 值 +
# case_id + 允许值列表, 业务异常也能查到。
BUG_RB1 = "RB1"

# M9-2 修复: result_writer.write_step_result 的 result_data 写
# status="SUCCESS"/"FAIL" 字面量, 跟 M9 修的 8 个 step_content 不一致。
# 当 status 列改成 enum 类型时会写错值, 静默存错。
# 修: 统一走 StepStatusEnum.SUCCESS / .FAIL。
BUG_M9_2 = "M9-2"

# RB2 修复: InterfaceRunner.run_interface_by_task 函数体漏调
# init_global_headers(), 跟另外 3 个入口 (try_interface / try_group /
# run_interface_case) 行为不一致。任务执行时 g_headers 永远为 [],
# 用户配的全局 header (Authorization / X-Tenant-Id) 全部丢失。
# 修: 函数体开头加 await self.init_global_headers()。
BUG_RB2 = "RB2"

# DOC 修复: InterfaceCaseResultMapper.recompute_case_result_nums
# 之前 session=None 直接 raise ValueError, 但 docstring + 调用方
# 注释 (result_writer.py:367) 都写 "自管事务", 实际静默 except, 丢对账。
# 修: session=None 时开自己的 cls.transaction(), 跟 D4 哲学一致。
BUG_DOC = "DOC"
