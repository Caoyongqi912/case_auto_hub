import asyncio
import copy
import json
from typing import List, Dict, Any, Mapping, TypeVar, Tuple
from httpx import Response
from app.mapper.interface.interfaceGroupMapper import InterfaceGroupMapper
from app.mapper.interface.interfaceVarsMapper import InterfaceVarsMapper
from app.mapper.project.dbConfigMapper import DbConfigMapper
from app.mapper.project.env import EnvMapper
from app.model.base import EnvModel
from app.model.interface import InterfaceModel, InterfaceCaseResultModel, InterFaceCaseModel, InterfaceTaskResultModel, \
    InterfaceVariables, InterfaceResultModel
from app.model.interface.InterfaceCaseStepContent import InterfaceCaseStepContent, InterfaceCondition, \
    InterfaceLoopModal
from app.model.interface.interfaceResultModel import InterfaceGroupResult, InterfaceCaseStepContentResult
from enums import InterfaceExtractTargetVariablesEnum, InterfaceResponseStatusCodeEnum, InterfaceAPIResultEnum, \
    InterfaceCaseErrorStep
from enums.CaseEnum import CaseStepContentType, LoopTypeEnum
from play.starter import UIStarter
from utils import MyLoguru, GenerateTools
from app.mapper.interface import InterfaceMapper, InterfaceConditionMapper, InterfaceGroupResultMapper
from app.mapper.interface.interfaceCaseMapper import InterfaceCaseMapper, InterfaceCaseContentDBExecuteMapper, \
    InterfaceLoopMapper
from utils.assertsUtil import MyAsserts
from utils.execDBScript import ExecDBScript
from interface.exec import *
from utils.variableTrans import VariableTrans
from .middleware import HttpxMiddleware
from .starter import APIStarter
from .writer import InterfaceAPIWriter, InitInterfaceCaseResult
from .types import *
log = MyLoguru().get_logger()



class InterFaceRunner:
    DEFAULT_CUSTOM_ENV_ID = 99999
    __slots__ = ("starter", "vars", "sender")

    def __init__(self, starter: APIStarter | UIStarter):
        self.starter = starter
        self.vars = VariableTrans()
        self.sender = HttpxMiddleware(self.vars, self.starter)

    async def get_interface(self, interfaceId: int, use_var: bool = False):
        """获取接口信息"""
        interface = await InterfaceMapper.get_by_id(ident=interfaceId)
        # 自定义环境
        if interface.env_id == self.DEFAULT_CUSTOM_ENV_ID:
            from utils import Tools
            parse = Tools.parse_url(interface.url)
            url = parse.path
            host = f"{parse.scheme}://{parse.netloc}"
        else:
            env = await EnvMapper.get_by_id(ident=interface.env_id)
            host = env.host
            url = interface.url
            if env.port:
                host += f":{env.port}"
        if use_var:
            # 1、前置变量参数
            await self.__exec_before_params(interface.before_params)
            # 2、执行前置函数
            await self.__exec_script(interface.before_script)
            # 3.前置sql
            await self.__exec_before_sql(interface)
            url = await self.vars.trans(target=url)
        info = await self.sender.set_req_info(interface)
        info.pop("follow_redirects")
        info.pop("read")
        info.pop("connect")
        return {
            "name": interface.name,
            "method": interface.method.lower(),
            "url": url,
            "host": host,
            "asserts": interface.asserts,
            **info
        }

    async def execute_interface_by_ui(self, interface: InterfaceAPI, ui_vars: VARS):
        """
        ui 侧执行接口
        :param interface：接口对象
        :param ui_vars: ui 变量
        """
        if ui_vars:
            await self.vars.add_vars(ui_vars)
        # env 使用默认接口env
        result, _ = await self.__execute_interface(interface)
        return result, _

    async def try_interface(self, interface_id: int, env_id: int) -> Mapping[str, Any]:
        """
        执行单个接口请求调试
        无变量、有前置方法、
        需要返回response
        """
        interface = await InterfaceMapper.get_by_id(ident=interface_id)
        env = await EnvMapper.get_by_id(ident=env_id)
        result, _ = await self.__execute_interface(interface=interface, env=env)
        return result

    async def try_group(self, groupId: int, env_id: int):
        """
        执行接口组
        :param groupId 组ID
        :param env_id  环境ID
        """
        interfaces = await InterfaceGroupMapper.query_apis(groupId=groupId)
        env = await EnvMapper.get_by_id(env_id)
        results = []
        for interface in interfaces:
            await self.starter.send(f"✍️✍️  Execute    {interface}")
            result, _ = await self.__execute_interface(interface=interface, env=env)
            results.append(result)
        return results

    async def run_interface_by_task(self, interface: InterfaceAPI,
                                    taskResult: InterfaceTaskResult,
                                    retry: int = 0,
                                    retry_interval: int = 0,
                                    env: Env = None) -> bool:
        """
        任务执行api
        :param interface: 接口对象
        :param taskResult: 任务结果对象
        :param env: 环境配置
        :param retry: 重试次数
        :param retry_interval: 重试间隔
        :return: 执行是否成功
        """
        for attempt in range(retry + 1):
            result, success = await self.__execute_interface(interface=interface, task_result=taskResult, env=env)

            # 成功则记录结果并返回
            if success:
                await InterfaceAPIWriter.write_interface_result(**result)
                return True

            # 最后一次重试失败，记录结果并返回False
            if attempt == retry:
                await InterfaceAPIWriter.write_interface_result(**result)
                await self.starter.send(f"接口 {interface} 执行结果 FALSE")
                return False

            # 进行重试
            await self.starter.send(f"接口 {interface} 执行结果 FALSE 第 {attempt + 1} 次重试")
            if retry_interval:
                await asyncio.sleep(retry_interval)

    async def run_interface_case(self,
                                 interfaceCaseId: int,
                                 env_id: int | Env,
                                 error_stop: bool,
                                 task: InterfaceTaskResult = None) -> tuple[bool, InterfaceCaseResult]:
        """
        业务流用例执行
        :param interfaceCaseId 业务流 id
        :param env_id 执行环境
        :param error_stop 遇错停止
        :param task 任务执行
        """
        # 查询用例
        interfaceCase = await InterfaceCaseMapper.get_by_id(ident=interfaceCaseId)
        log.info(f"查询到业务流用例  {interfaceCase}")
        if not interfaceCase:
            await self.starter.send(f"未找到用例 {interfaceCaseId}")
            return await self.starter.over()

        # 查询用例步骤内容
        case_steps = await InterfaceCaseMapper.query_content(case_id=interfaceCaseId)

        await self.starter.send(f"用例 {interfaceCase.title} 执行开始。执行人 {self.starter.username}")
        await self.starter.send(f"查询到关联Step x {len(case_steps)} ...")

        if not case_steps:
            await self.starter.send("无可执行步骤，结束执行")
            return await self.starter.over()

        await self.__init_interface_case_vars(interfaceCase)
        log.info(f"加载用例专属变量 = {self.vars}")

        if isinstance(env_id, int):
            target_env = await EnvMapper.get_by_id(ident=env_id)
        else:
            target_env = env_id  # aka env 兼容 TASK
        await self.starter.send(f"✍️✍️ 使用环境 {target_env}")

        case_result = await InterfaceAPIWriter.init_interface_case_result(
            InitInterfaceCaseResult(interface_case=interfaceCase,
                                    env=target_env,
                                    task=task,
                                    starter=self.starter))
        log.info(f"初始化用例结果对象 = {case_result}")
        flag = True

        try:
            for index, _step_content in enumerate(case_steps, start=1):
                await self.starter.send(f"✍️✍️ {'=' * 20} EXECUTE_STEP {index} ： {_step_content} {'=' * 20}")
                case_result.progress = round(index / len(case_steps), 2) * 100
                # 步骤开关旨在 用例调试中使用 任务执行默认开启
                if _step_content.enable == 0 and not task:
                    await self.starter.send(f"✍️✍️  EXECUTE_STEP {index} ： 调试禁用 跳过执行")
                    continue

                # 如果 flag 已经是 False 且需要错误停止，则跳过后续步骤
                if not flag and error_stop == InterfaceCaseErrorStep.STOP:
                    await self.starter.send(f"⏭️⏭️  SKIP_STEP {index} ： 遇到错误已停止")
                    continue

                step_result = True
                match _step_content.content_type:
                    # ================================ 执行LOOP ================================
                    case CaseStepContentType.STEP_LOOP:
                        await self.__execute_loop_content(
                            step_index=index,
                            case_step=_step_content,
                            env=target_env,
                            case_result=case_result,
                            interface_task_result_id=task.id if task else None

                        )
                        continue
                    # ================================ 执行DB ================================
                    case CaseStepContentType.STEP_API_DB:
                        _extract = await self.__execute_content_sql(case_step=_step_content)
                        await InterfaceAPIWriter.set_case_step_content_api_db_result(
                            step_index=index,
                            interface_case_result_id=case_result.id,
                            step_content=_step_content,
                            starter=self.starter,
                            interface_task_result_id=task.id if task else None,
                            script_vars=_extract
                        )
                        continue

                    # ================================ 执行等待 ================================
                    case CaseStepContentType.STEP_API_WAIT:
                        await self.starter.send(f"⏰⏰  等待 {_step_content.api_wait_time} 秒")
                        await asyncio.sleep(_step_content.api_wait_time)
                        await InterfaceAPIWriter.set_case_step_content_api_wait_result(
                            step_index=index,
                            interface_case_result_id=case_result.id,
                            step_content=_step_content,
                            starter=self.starter,
                            interface_task_result_id=task.id if task else None
                        )
                        continue
                    # ================================ 执行脚本 ================================
                    case CaseStepContentType.STEP_API_SCRIPT:
                        temp_vars = await self.__exec_script(script=_step_content.api_script_text,
                                                             target=InterfaceExtractTargetVariablesEnum.StepScript)
                        await InterfaceAPIWriter.set_case_step_content_api_script_vars_result(
                            step_index=index,
                            interface_case_result_id=case_result.id,
                            step_content=_step_content,
                            starter=self.starter,
                            script_vars=temp_vars,
                            interface_task_result_id=task.id if task else None
                        )
                        continue
                    # ============================= 执行单接口 =============================
                    case CaseStepContentType.STEP_API:
                        step_result, interface_result = await self.__execute_single_api(
                            interface_id=_step_content.target_id,
                            env=target_env,
                            case_result=case_result
                        )
                        log.debug(f"case_result  step_result= {step_result}")
                        # 写 API content
                        await InterfaceAPIWriter.set_case_step_content_api_result(
                            step_content=_step_content,
                            step_index=index,
                            flag=step_result,
                            interface_result=interface_result,
                            interface_case_result_id=case_result.id,
                            interface_task_result_id=task.id if task else None,
                        )
                    # ============================= 执行接口组 =============================
                    case CaseStepContentType.STEP_API_GROUP:
                        start_time = GenerateTools.getTime(1)
                        step_result, group_result = await self.__execute_group_apis(case_step=_step_content,
                                                                                    env=target_env,
                                                                                    case_result=case_result)
                        log.debug(f"STEP_API_GROUP  STEP_API_GROUP= {step_result}")

                        await InterfaceAPIWriter.set_case_step_content_api_group_result(
                            step_index=index,
                            interface_case_result_id=case_result.id,
                            interface_task_result_id=task.id if task else None,
                            group_result=group_result,
                            step_content=_step_content,
                            flag=step_result,
                            starter=self.starter,
                            start_time=start_time,
                        )
                    # ============================= 执行条件 =============================
                    case CaseStepContentType.STEP_API_CONDITION:
                        step_result = await  self.__execute_condition_apis(
                            step_index=index,
                            case_step=_step_content,
                            env=target_env,
                            case_result=case_result,
                            task_result=task)
                    # ============================= 断言 =============================
                    case CaseStepContentType.STEP_API_ASSERT:
                        step_result, assert_data = await self.__exec_content_assert(content=_step_content,
                                                                                    case_result=case_result)
                        await InterfaceAPIWriter.set_case_step_content_api_assert_result(
                            step_index=index,
                            interface_case_result_id=case_result.id,
                            interface_task_result_id=task.id if task else None,
                            assert_data=assert_data,
                            step_content=_step_content,
                            starter=self.starter
                        )

                # 一旦 flag 变为 False，就不再变回 True
                flag = flag and step_result

                # 遇到错停止
                if not flag and interfaceCase.error_stop == InterfaceCaseErrorStep.STOP:
                    case_result.progress = 100
                    break
                log.debug(f"case_result ===== {case_result}")
                await InterfaceAPIWriter.write_process(case_result=case_result)
                await self.starter.send(f"\n")

            await self.starter.send(f"用例 {interfaceCase.title} 执行结束")
            await self.starter.send(f"{'====' * 20}")
            case_result.interfaceLog = "".join(self.starter.logs)
            await InterfaceAPIWriter.write_interface_case_result(case_result=case_result)
            return flag, case_result
        except Exception as e:
            log.exception(e)
            return False, case_result
        finally:
            await self.vars.clear()
            await self.starter.over(case_result.id)

    async def __execute_loop_content(self, step_index: int, case_step: InterfaceCaseStepContent,
                                     env: Env,
                                     case_result: InterfaceCaseResult,
                                     interface_task_result_id: int = None):
        """
        loop 执行
        :param case_step:
        :return:
        """
        loop = await InterfaceLoopMapper.get_by_id(ident=case_step.target_id)
        loop_steps = await InterfaceLoopMapper.query_loop_apis_by_content_id(loop_id=case_step.target_id)
        # 记录条件执行结果
        start_time = GenerateTools.getTime(1)
        _content_result = await InterfaceAPIWriter.init_case_step_loop_result(
            step_index=step_index,
            interface_case_result_id=case_result.id,
            interface_task_result_id=interface_task_result_id,
            step_content=case_step,
            starter=self.starter,
            start_time=start_time,
        )
        match loop.loop_type:
            case LoopTypeEnum.LoopTimes:
                return await self.__execute_loop_times(
                    loop=loop,
                    api_steps=loop_steps,
                    env=env,
                    content_result=_content_result
                )
            case LoopTypeEnum.LoopItems:
                return await self.__execute_loop_items(
                    loop=loop,
                    api_steps=loop_steps,
                    env=env,
                    content_result=_content_result
                )
            case LoopTypeEnum.LoopCondition:
                return await self.__execute_loop_condition(
                    loop=loop,
                    api_steps=loop_steps,
                    env=env,
                    content_result=_content_result
                )
            case _:
                return

    async def __execute_loop_times(self, loop: Loop, api_steps: List[InterfaceAPI], env: Env,
                           content_result: InterfaceContentResult):
        """
        times 循环

        全部执行完  不论对错
        全对 content result = true
        case success +1
        :param loop:
        :param api_steps:
        :return:
        """
        ALL_SUCCESS = True
        for i in range(loop.loop_times):
            for index, interface in enumerate(api_steps, start=1):
                await self.starter.send(
                    f"✍️✍️  {'-' * 20} 次数循环步骤 次数{i}   {interface.name} {'-' * 20}"
                )
                # 执行单个接口
                result, api_success = await self.__execute_interface(
                    interface=interface, env=env
                )

                # 记录接口执行结果
                await InterfaceAPIWriter.write_interface_result(
                    interface_loop_result_id=content_result.id,
                    **result
                )
                if api_success is False:
                    ALL_SUCCESS = False
                if loop.loop_interval > 0:
                    await asyncio.sleep(loop.loop_interval)
        content_result.content_result = ALL_SUCCESS
        await InterfaceAPIWriter.set_content_finally_result(content_result)

    async def __execute_loop_items(self, loop: Loop, api_steps: List[InterfaceAPI], env: Env,
                           content_result: InterfaceContentResult):
        """
        items 遍历
        :param loop:
            a = "1,2,3,4"
            b = [1,2,3,4]
            c = "{{a}},b,c,e"

        :param api_steps:
        :return:
        """
        try:
            items = json.loads(loop.loop_items)
        except json.JSONDecodeError:
            items = [item.strip() for item in loop.loop_items.split(',') if item.strip()]
        ALL_SUCCESS = True
        if items:
            total_apis = len(api_steps)
            for item in items:
                for index, interface in enumerate(api_steps, start=1):
                    ItemKey = loop.loop_item_key
                    await self.starter.send(
                        f"✍️✍️  {'-' * 20} 执行数组循环步骤 [{ItemKey}:{item}] {index}/{total_apis}: "
                        f"{interface.name} {'-' * 20}"
                    )
                    # await self.vars.add_var(key=ItemKey, value=item)
                    # 执行单个接口
                    result, api_success = await self.__execute_interface(
                        interface=interface, env=env,
                        temp_vars={"key": ItemKey,
                                   InterfaceExtractTargetVariablesEnum.Target: InterfaceExtractTargetVariablesEnum.LOOP,
                                   "value": item}
                    )

                    # 记录接口执行结果
                    await InterfaceAPIWriter.write_interface_result(
                        interface_loop_result_id=content_result.id,
                        **result
                    )
                    if api_success is False:
                        ALL_SUCCESS = False
                    if loop.loop_interval > 0:
                        await asyncio.sleep(loop.loop_interval)
        content_result.content_result = ALL_SUCCESS
        await InterfaceAPIWriter.set_content_finally_result(content_result)

    async def __execute_loop_condition(self, loop: Loop, api_steps: List[InterfaceAPI], env: Env,
                               content_result: InterfaceContentResult):
        """
        条件 循环

        :param loop:
            key: str  'abc' '{{name}}'
            value: str 1
            operator: int
        :param api_steps:
        :return:
        """
        # 执行条件判断
        _execCondition = ExecCondition(self.vars)
        n = 0
        LOOP_SUCCESS = True
        while True:
            n += 1
            for index, interface in enumerate(api_steps, start=1):
                await self.starter.send(
                    f"✍️✍️  {'-' * 20} 执行循环步骤  {n} times: "
                    f"{interface.name} {'-' * 20}"
                )
                # 执行单个接口
                result, api_success = await self.__execute_interface(
                    interface=interface, env=env
                )
                if api_success is False:
                    LOOP_SUCCESS = False
                # 记录接口执行结果
                await InterfaceAPIWriter.write_interface_result(
                    interface_loop_result_id=content_result.id,
                    **result
                )
                if loop.loop_interval > 0:
                    LOOP_SUCCESS = False

                    await asyncio.sleep(loop.loop_interval)

            key = await self.vars.trans(loop.key)
            log.info(f"__loop_condition  key = {key}")
            value = await self.vars.trans(loop.value)
            log.info(f"__loop_condition  value = {value}")
            log.info(f"__loop_condition  operate = {loop.operate}")
            if n > loop.max_loop:
                await self.starter.send(
                    f"✍️✍️  执行循环步骤  {n} times: 循环次数超过最大限制"
                )
                break
            try:
                MyAsserts.option(
                    assertOpt=loop.operate,
                    expect=key,
                    actual=value
                )
                LOOP_SUCCESS = True
                break
            except AssertionError:
                await self.starter.send(
                    f"✍️✍️  执行循环步骤  {n} times: 断言失败 key = {key} type = {type(key)}  value = {value} type = {type(value)}"
                )
                continue
        content_result.content_result = LOOP_SUCCESS
        await InterfaceAPIWriter.set_content_finally_result(content_result)

    async def __execute_single_api(self,
                                   interface_id: int,
                                   env: Env,
                                   case_result: InterfaceCaseResult) -> tuple[bool, InterfaceResultModel]:
        """
        api类型用例执行

        return tuple (flag, interface_result.id)
        """
        interface = await InterfaceMapper.get_by_id(ident=interface_id)
        result, flag = await self.__execute_interface(interface=interface, env=env, case_result=case_result)
        interface_result = await InterfaceAPIWriter.write_interface_result(**result)
        if flag:
            case_result.success_num += 1
        else:
            case_result.result = InterfaceAPIResultEnum.ERROR
            case_result.fail_num += 1
        return flag, interface_result

    async def __execute_content_sql(self, case_step: InterfaceCaseStepContent):
        """
        步骤SQL 执行
        """
        content_sql = await InterfaceCaseContentDBExecuteMapper.get_by_id(ident=case_step.target_id)
        if not content_sql:
            return []

        _db = await DbConfigMapper.get_by_id(ident=content_sql.db_id)
        if not _db:
            log.warning(f"未找到数据库配置 ID: {content_sql.db_id}")
            return []

        script = await self.vars.trans(content_sql.sql_text.strip())
        db_script = ExecDBScript(self.starter, script, content_sql.sql_extracts)
        res = await db_script.invoke(_db.db_type, **_db.config)
        await self.vars.add_vars(res)
        await self.starter.send(f"🫳🫳    数据库读取 = {json.dumps(res, ensure_ascii=False)}")

        if res:
            _vars = [
                {
                    InterfaceExtractTargetVariablesEnum.KEY: k,
                    InterfaceExtractTargetVariablesEnum.VALUE: v,
                    InterfaceExtractTargetVariablesEnum.Target: InterfaceExtractTargetVariablesEnum.ContentSQL
                }
                for k, v in res.items()
            ]
            return _vars
        return []

    async def __execute_condition_apis(self,
                                       step_index: int,
                                       case_step: InterfaceCaseStepContent,
                                       case_result: InterfaceCaseResult,
                                       env: Env,
                                       task_result: InterfaceTaskResult = None,
                                       ) -> bool:
        """
        执行逻辑判断
        if true:
            exec apis
        else:
            return True

        condition_result
            - interface_result
            - interface_result
            - interface_result

        :param case_result 用例结果模型
        :param env 执行环境
        :param case_step  用例步骤
        """
        start_time = GenerateTools.getTime(1)
        condition: InterfaceCondition = await InterfaceConditionMapper.get_by_id(ident=case_step.target_id)
        # 执行条件判断
        _execCondition = ExecCondition(self.vars)
        condition_passed, content_condition = await _execCondition.invoke(condition, self.starter)

        # 记录条件执行结果
        _content_result = await InterfaceAPIWriter.set_case_step_content_api_condition_result(
            step_index=step_index,
            interface_case_result_id=case_result.id,
            interface_task_result_id=task_result.id if task_result else None,
            step_content=case_step,
            starter=self.starter,
            start_time=start_time,
            content_condition=content_condition,
        )
        #  根据条件结果处理
        if condition_passed:
            await self.starter.send("✍️✍️  执行条件判断通过 🎉🎉")

            # 获取条件关联的API列表
            condition_apis = await InterfaceConditionMapper.query_condition_apis_by_content_id(
                condition.id
            )
            # 如果没有关联API，直接返回成功
            if not condition_apis:
                _content_result.content_result = True
                await InterfaceAPIWriter.set_content_finally_result(_content_result)
                case_result.success_num += 1
                return True
            # 执行所有关联的API
            total_apis = len(condition_apis)
            for index, interface in enumerate(condition_apis, start=1):
                await self.starter.send(
                    f"✍️✍️  {'-' * 20} 执行条件步骤 {index}/{total_apis}: "
                    f"{interface.name} {'-' * 20}"
                )
                # 执行单个接口
                result, api_success = await self.__execute_interface(
                    interface=interface, env=env, case_result=case_result
                )

                # 记录接口执行结果
                await InterfaceAPIWriter.write_interface_result(
                    interface_condition_result_id=_content_result.id,
                    **result
                )

                # 如果执行失败，停止后续执行
                if not api_success:
                    await self.starter.send(f"✍️✍️  步骤 {index}/{total_apis} 执行失败，停止后续执行")
                    case_result.result = InterfaceAPIResultEnum.ERROR
                    case_result.fail_num += 1
                    _content_result.content_result = False
                    await InterfaceAPIWriter.set_content_finally_result(_content_result)
                    return False

                # 执行成功，统计成功数量
                case_result.success_num += 1

            # 所有API执行成功
            _content_result.content_result = True
            await InterfaceAPIWriter.set_content_finally_result(_content_result)
            return True
        else:
            # 条件未通过，跳过子步骤
            await self.starter.send("✍️✍️  执行条件判断未通过 ❌❌  跳过子步骤")
            case_result.success_num += 1
            _content_result.content_result = True
            await InterfaceAPIWriter.set_content_finally_result(_content_result)
            return True

    async def __execute_group_apis(self,
                                   case_step: InterfaceCaseStepContent,
                                   env: Env,
                                   case_result: InterfaceCaseResult) -> tuple[bool, InterfaceGroupResult]:
        """
        组内 API执行
        :param case_result 用例结果模型
        :param env 执行环境
        :param case_step  用例步骤
        """

        interfaces = await InterfaceGroupMapper.query_apis(groupId=case_step.target_id)
        # 初始化GROUP RESULT
        group_result = await InterfaceGroupResultMapper.init_model(
            group_name=case_step.content_name,
            group_api_num=len(interfaces),
            interface_case_result_id=case_result.id
        )

        if not interfaces:
            return True, group_result

        log.info(f"group result init {group_result}")

        for index, interface in enumerate(interfaces, start=1):
            await self.starter.send(f"✍️✍️  EXECUTE GROUP STEP {index} : {interface}")
            result, flag = await self.__execute_interface(interface=interface, env=env, case_result=case_result)
            # 写API结果 关联Group result
            await InterfaceAPIWriter.write_interface_result(interface_group_result_id=group_result.id, **result)
            # 报错停止
            if not flag:
                case_result.result = InterfaceAPIResultEnum.ERROR
                case_result.fail_num += 1
                return False, group_result
        case_result.success_num += 1
        return True, group_result

    async def __execute_interface(self,
                                  interface: InterfaceAPI,
                                  env: Env = None,
                                  case_result: InterfaceCaseResult = None,
                                  task_result: InterfaceTaskResult = None,
                                  temp_vars: VARS = None
                                  ) -> Tuple[Mapping[str, Any], bool]:
        """接口执行

        Args:
            interface (InterfaceAPI): 接口对象
            env (Env, optional): 运行环境. Defaults to None.
            case_result (InterfaceCaseResult, optional): 业务流结果对象. Defaults to None.
            task_result (InterfaceTaskResult, optional): 任务结果对象. Defaults to None.
            temp_vars (VARS, optional): 临时变量. Defaults to None.

        Returns:
            Tuple[Mapping[str, Any], bool] 结果，是否成功
        """
        temp_variables = []
        if temp_vars:
            if isinstance(temp_vars, list):
                temp_variables.extend(temp_vars)
            else:
                temp_variables.append(temp_vars)
        asserts_info = None
        request_info = None
        response = None
        url = None
        # 记录请求时间
        t = GenerateTools.getTime(1)
        await self.starter.send(f"✍️✍️  EXECUTE API : {interface} ")
        try:
            # 1、接口处理请求URL
            url = await self.set_url(interface, env)

            # 2. 执行前置操作
            temp_variables.extend(await self.__exec_before_params(interface.before_params))
            temp_variables.extend(await self.__exec_script(interface.before_script))
            temp_variables.extend(await self.__exec_before_sql(interface))

            # 3. 准备请求数据并替换变量
            request_info = await self.sender.set_req_info(interface)
            resolved_url = await self.vars.trans(url)

            # 4. 执行接口请求
            response = await self.sender(url=resolved_url, method=interface.method, **request_info)

            # 5. 执行后置操作
            asserts_info = await self.__exec_assert(response=response, interface=interface)
            temp_variables.extend(await self.__exec_extract(response=response, interface=interface))
            temp_variables.extend(await self.__exec_script(interface.after_script))

        except Exception as e:
            log.exception(e)
            await self.starter.send(f"Error occurred: \"{str(e)}\"")
            response = f"{str(e)} to {url}"
        finally:
            request_info['url'] = url
            return await  InterfaceAPIWriter.set_interface_result_info(
                startTime=t,
                starter=self.starter,
                request_info=request_info,
                interface=interface,
                response=response,
                asserts=asserts_info,
                case_result=case_result,
                task_result=task_result,
                variables=temp_variables
            )

    async def __exec_script(self, script: str,
                            target=InterfaceExtractTargetVariablesEnum.BeforeScript) -> VARS:
        """
        执行脚本

        Args:
            script (f): 脚本内容
            target (_type_, optional): Defaults to InterfaceExtractTargetVariablesEnum.BeforeScript.

        Returns:
            VARS: 提取变量
        """
        if script:
            exe = ExecSafeScript()
            _extracted_vars = exe.execute(script)
            await self.vars.add_vars(_extracted_vars)
            await self.starter.send(f"🫳🫳  脚本 = {json.dumps(_extracted_vars, ensure_ascii=False)}")
            _vars = [
                {
                    InterfaceExtractTargetVariablesEnum.KEY: k,
                    InterfaceExtractTargetVariablesEnum.VALUE: v,
                    InterfaceExtractTargetVariablesEnum.Target: target
                }
                for k, v in _extracted_vars.items()
            ]
            return _vars
        return []

    async def __exec_before_params(self, before_params: List[Dict[str, Any]] = None):
        """处理前置参数

        添加到全局变量
        返回局域变量
        """
        if before_params:
            values = await self.vars.trans(before_params)
            log.debug(f"before params {values}")
            await self.vars.add_vars(values)
            _vars = [
                {
                    **item,
                    InterfaceExtractTargetVariablesEnum.Target: InterfaceExtractTargetVariablesEnum.BeforeParams
                }
                for item in values
            ]
            return _vars
        return []

    async def __exec_before_sql(self, interface: InterfaceAPI):
        """
        执行前置sql 操作

        ## Select
            sql:str
            - select username from user => [{username:xxx}{username:xxx}][0]
            - select username as un  from user => [{un:xxx}{un:xxx}][0]

            sql_extracts: [{key:username,jp:$[0].username},{key:username,jp:$[1].username}]
            - select username from user => [{username:xxx}{username:xxx}]
            ==>  [{username:xx},{username:xx}]
        ## Update
        """

        # 不执行
        if not interface.before_sql or not interface.before_db_id:
            return []
        _db = await DbConfigMapper.get_by_id(interface.before_db_id)
        if not _db:
            log.warning(f"未找到数据库配置 ID: {interface.before_db_id}")
            return []
        script = await self.vars.trans(interface.before_sql.strip())
        db_script = ExecDBScript(self.starter, script, interface.before_sql_extracts)
        res = await db_script.invoke(_db.db_type, **_db.config)
        await self.vars.add_vars(res)
        await self.starter.send(f"🫳🫳    数据库读取 = {json.dumps(res, ensure_ascii=False)}")

        if res:
            _vars = [
                {
                    InterfaceExtractTargetVariablesEnum.KEY: k,
                    InterfaceExtractTargetVariablesEnum.VALUE: v,
                    InterfaceExtractTargetVariablesEnum.Target: InterfaceExtractTargetVariablesEnum.BeforeSQL
                }
                for k, v in res.items()
            ]
            return _vars
        return []

    async def __exec_content_assert(self,
                                    content: InterfaceCaseStepContent,
                                    case_result: InterfaceCaseResult
                                    ) -> tuple[bool, list[dict[str, Any]] | None]:
        """
        步骤 断言
        """
        try:
            _assert_exec = ExecAsserts(variables=self.vars())
            assert_list_info, assert_success = await  _assert_exec.assert_content_list(content)
            if not assert_list_info:
                await self.starter.send(
                    f"🆚🆚 断言:  ⚠️⚠️ 未配置断言")
                return True, None
            if assert_success is False:
                case_result.fail_num += 1
            else:
                case_result.success_num += 1
            return assert_success, assert_list_info
        except Exception as e:
            log.exception(e)
            await self.starter.send(f"⚠️⚠️ 步骤断言异常: {str(e)}")
            return False, None

    async def __exec_assert(self, response: Response, interface: InterfaceAPI):
        """
        响应断言
        前提：
        1、有断言
        2、有响应
        """
        _assert = ExecAsserts(response, self.vars())
        asserts_info = await _assert(interface.asserts)
        if asserts_info:
            await self.starter.send(f"🫳🫳  响应断言 = {json.dumps(asserts_info, ensure_ascii=False)}")
        else:
            await self.starter.send(f"🫳🫳  未配置 响应断言 ⚠️⚠️")
        return asserts_info

    async def __exec_extract(self, response: Response, interface: InterfaceAPI):
        """
        变量提取
        前提：
        1、有断言
        2、有响应
        3、响应200
        """
        if interface.extracts and response.status_code == InterfaceResponseStatusCodeEnum.SUCCESS:
            _extract = ExecResponseExtract(response=response)
            _interface_extract = copy.deepcopy(interface.extracts)  #
            _vars = await _extract(_interface_extract)
            await self.starter.send(f"🫳🫳  响应参数提取 = {[{v.get('key'): v.get('value')} for v in _vars]}")
            await self.vars.add_vars(_vars)
            return _vars
        return []

    async def __init_interface_case_vars(self, interfaceCase: InterFaceCaseModel):
        """
        用例执行
        初始化用例变量
        """
        try:
            interfaceCaseVars: List[InterfaceVariables] = await InterfaceVarsMapper.query_by(case_id=interfaceCase.id)
            if interfaceCaseVars:
                for iar in interfaceCaseVars:
                    _v = await self.vars.trans(iar.value)
                    await self.vars.add_vars({iar.key: _v})
            if self.vars():
                await self.starter.send(f"🫳🫳 初始化用例变量 = {json.dumps(self.vars(), ensure_ascii=False)}")
        except Exception as e:
            log.error(e)

    async def set_url(self, interface: InterfaceAPI, env: Env = None):
        """
        设置请求地址
        """
        try:
            if interface.env_id == self.DEFAULT_CUSTOM_ENV_ID:
                log.info(f"请求环境 {interface.url}")  # 优先级最高。不进行替换
                return interface.url
            if env is None:  # 兼容UI 等
                env = await EnvMapper.get_by_id(interface.env_id)

            url = f"{env.url}{interface.url}"
            log.info(f"请求环境 {url}")
            return url
        except Exception as e:
            log.error(f"设置请求url失败 = {e}")
            raise ValueError("请求环境不存在、请检查")
