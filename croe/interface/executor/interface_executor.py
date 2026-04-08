#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Interface Executor

接口执行器
负责执行接口请求、处理前置/后置逻辑、断言验证和变量提取
"""
import copy
import json
from typing import Union, Tuple, Any, Dict, List, TypeVar, Optional

import httpx

from app.mapper.interface import InterfaceMapper
from app.mapper.project.dbConfigMapper import DbConfigMapper
from app.mapper.project.env import EnvMapper
from app.model.base import EnvModel
from app.model.interfaceAPIModel.interfaceModel import Interface
from common.httpxClient import HttpxClient
from croe.a_manager import ScriptManager, VariableManager
from croe.a_manager.assert_manager import AssertManager
from croe.interface.builder.request_builder import RequestBuilder
from croe.interface.builder.url_builder import UrlBuilder
from croe.interface.manager.extract_manager import ExtractManager
from croe.interface.starter import APIStarter
from croe.interface.types import InterfaceResultInfo, VARS
from croe.play.starter import UIStarter
from enums import ExtractTargetVariablesEnum, InterfaceAPIResultEnum, InterfaceResponseStatusCodeEnum
from utils import GenerateTools, log
from utils.execDBScript import ExecDBScript

BeforeParams = TypeVar("BeforeParams", bound=Union[List[Dict[str, Any]]])


class InterfaceExecutor:
    """
    接口执行器

    负责执行单个接口请求，包括：
    - 构建和执行 HTTP 请求
    - 处理前置参数、脚本和 SQL
    - 执行响应断言
    - 提取变量
    """

    def __init__(self, starter: Union[UIStarter, APIStarter], variable_manager: VariableManager):
        """
        初始化接口执行器

        Args:
            starter: 启动器（UI 或 API）
            variable_manager: 变量管理器
        """
        self.variable_manager = variable_manager
        self.starter = starter
        self.http = HttpxClient(logger=self.starter.send)

    async def request_info(self, request_id: int, use_var: bool = False) -> Dict[str, Any]:
        """
        获取请求信息

        Args:
            request_id: 请求 ID
            use_var: 是否使用变量

        Returns:
            请求信息字典
        """
        interface = await InterfaceMapper.get_by_id(ident=request_id)

        if interface.interface_env_id == UrlBuilder.CUSTOM_ENV_ID:
            from utils import Tools
            parse = Tools.parse_url(interface.interface_url)
            url = parse.path
            host = f"{parse.scheme}://{parse.netloc}"
        else:
            env = await EnvMapper.get_by_id(ident=interface.interface_env_id)
            host = env.host
            url = interface.interface_url
            if env.port:
                host += f":{env.port}"

        if use_var:
            await self.__execute_before_params(interface.interface_before_params)
            await self.__execute_before_script(interface.interface_before_script)
            await self.__execute_before_sql(interface)
            url = await self.variable_manager.trans(target=url)

        builder = RequestBuilder(self.variable_manager)
        request_info = await builder.set_req_info(interface)
        request_info.pop("follow_redirects")
        request_info.pop("read")
        request_info.pop("connect")

        return {
            "name": interface.interface_name,
            "method": interface.interface_method.lower(),
            "url": url,
            "host": host,
            "asserts": interface.interface_asserts,
            **request_info
        }

    async def execute(
            self,
            interface: Interface,
            env: Optional[EnvModel] = None,
            case_result: Optional[Any] = None,
            task_result: Optional[Any] = None,
            temp_var: Optional[VARS] = None
    ) -> Tuple[InterfaceResultInfo, bool]:
        """
        执行接口请求

        Args:
            interface: 接口对象
            env: 环境配置
            case_result: 用例结果
            task_result: 任务结果
            temp_var: 临时变量

        Returns:
            Tuple[接口结果信息, 是否执行成功]
        """
        temp_variables = await get_temp_variables(temp_var)
        start_time = GenerateTools.getTime(1)
        await self.starter.send(f"✍️✍️  EXECUTE API : {interface}")
        resolved_url = ""
        asserts_info = None
        request_info = None
        response = None

        try:
            origin_url = await UrlBuilder.build(interface=interface, env=env)
            temp_variables.extend(await self._before_execute(interface))

            builder = RequestBuilder(self.variable_manager)
            request_info = await builder.set_req_info(interface)

            resolved_url = await self.variable_manager.trans(origin_url)

            response = await self.http(
                url=resolved_url,
                method=interface.interface_method,
                **request_info
            )

            temp_variables.extend(
                await self.__execute_extract(response=response, interface=interface)
            )

            asserts_info = await self.__execute_assert(response=response, interface=interface)

        except Exception as e:
            log.exception(e)
            await self.starter.send(f"Error occurred: \"{str(e)}\"")
            response = f"{str(e)} to {resolved_url}"

        finally:
            request_info['url'] = resolved_url
            return await set_interface_result_info(
                startTime=start_time,
                starter=self.starter,
                request_info=request_info,
                interface=interface,
                response=response,
                asserts=asserts_info,
                case_result=case_result,
                task_result=task_result,
                variables=temp_variables
            )

    async def _before_execute(self, interface: Interface) -> List:
        """
        执行前处理

        包括：前置参数、前置脚本、前置 SQL

        Args:
            interface: 接口对象

        Returns:
            临时变量列表
        """
        temp_variables = []
        temp_variables.extend(
            await self.__execute_before_params(interface.interface_before_params)
        )
        temp_variables.extend(
            await self.__execute_before_script(interface.interface_before_script)
        )
        temp_variables.extend(
            await self.__execute_before_sql(interface)
        )
        return temp_variables

    async def __execute_before_params(
            self,
            before_params: Optional[BeforeParams] = None
    ) -> List:
        """
        执行前置参数处理

        Args:
            before_params: 前置参数

        Returns:
            处理后的变量列表
        """
        if not before_params:
            return []

        values = await self.variable_manager.trans(before_params)
        log.info(f"执行前参数处理: {values}")

        if values:
            await self.variable_manager.add_vars(values)
            return [
                {
                    **item,
                    ExtractTargetVariablesEnum.Target: ExtractTargetVariablesEnum.BeforeParams
                }
                for item in values
            ]
        return []

    async def __execute_before_sql(self, interface: Interface) -> List:
        """
        执行前置 SQL 处理

        Args:
            interface: 接口对象

        Returns:
            处理后的变量列表
        """
        if not interface.interface_before_sql or not interface.interface_before_db_id:
            return []

        db_config = await DbConfigMapper.get_by_id(interface.interface_before_db_id)
        if not db_config:
            await self.starter.send(
                f"数据库配置不存在，db_id = {interface.interface_before_db_id}"
            )
            return []

        db_script = await self.variable_manager.trans(
            interface.interface_before_sql.strip()
        )
        log.info(f"执行前sql处理: {db_script}")

        db_executor = ExecDBScript(
            self.starter,
            db_script,
            interface.interface_before_sql_extracts
        )
        result = await db_executor.invoke(db_config.db_type, **db_config.config)

        await self.variable_manager.add_vars(result)
        await self.starter.send(f"🫳🫳    数据库读取 = {result}")

        if result:
            return [
                {
                    ExtractTargetVariablesEnum.KEY: k,
                    ExtractTargetVariablesEnum.VALUE: v,
                    ExtractTargetVariablesEnum.Target: ExtractTargetVariablesEnum.BeforeSQL
                }
                for k, v in result.items()
            ]
        return []

    async def __execute_before_script(self, script: Optional[str]) -> List:
        """
        执行前置脚本处理

        Args:
            script: 脚本内容

        Returns:
            处理后的变量列表
        """
        if script:
            script_manager = ScriptManager()
            extracted_vars = script_manager.execute(script)
            await self.variable_manager.add_vars(extracted_vars)
            await self.starter.send(
                f"🫳🫳  脚本 = {json.dumps(extracted_vars, ensure_ascii=False)}"
            )
            return [
                {
                    ExtractTargetVariablesEnum.KEY: k,
                    ExtractTargetVariablesEnum.VALUE: v,
                    ExtractTargetVariablesEnum.Target: ExtractTargetVariablesEnum.BeforeScript
                }
                for k, v in extracted_vars.items()
            ]
        return []

    async def __execute_assert(
            self,
            response: httpx.Response,
            interface: Interface
    ) -> Optional[List]:
        """
        执行响应断言

        Args:
            response: HTTP 响应对象
            interface: 接口对象

        Returns:
            断言结果列表
        """
        assert_manager = AssertManager(response, self.variable_manager.variables)
        asserts_info = await assert_manager(interface.interface_asserts)

        if asserts_info:
            await self.starter.send(
                f"🫳🫳  响应断言 = {json.dumps(asserts_info, ensure_ascii=False)}"
            )
        else:
            await self.starter.send(f"🫳🫳  未配置 响应断言 ⚠️⚠️")

        return asserts_info

    async def __execute_extract(
            self,
            response: httpx.Response,
            interface: Interface
    ) -> List:
        """
        执行变量提取

        Args:
            response: HTTP 响应对象
            interface: 接口对象

        Returns:
            提取的变量列表
        """
        if (
            interface.interface_extracts
            and response.status_code == InterfaceResponseStatusCodeEnum.SUCCESS
        ):
            extract_manager = ExtractManager(response=response)
            interface_extracts = copy.deepcopy(interface.interface_extracts)
            vars_list = await extract_manager(interface_extracts)

            await self.starter.send(
                f"🫳🫳  响应参数提取 = {[{v.get('key'): v.get('value')} for v in vars_list]}"
            )
            await self.variable_manager.add_vars(vars_list)
            return vars_list
        return []


async def get_temp_variables(temp_vars: Optional[VARS]) -> List:
    """
    处理临时变量

    Args:
        temp_vars: 临时变量

    Returns:
        临时变量列表
    """
    temp_variables = []

    if temp_vars:
        if isinstance(temp_vars, list):
            temp_variables.extend(temp_vars)
        else:
            temp_variables.append(temp_vars)

    return temp_variables


async def set_interface_result_info(
        startTime: str,
        starter: APIStarter,
        interface: Interface,
        request_info: Optional[Dict[str, Any]] = None,
        response: Union[httpx.Response, str] = None,
        asserts: Optional[List] = None,
        case_result: Optional[Any] = None,
        variables: Optional[List] = None,
        task_result: Optional[Any] = None
) -> Tuple[Dict[str, Any], bool]:
    """
    设置接口结果信息

    构建完整的接口执行结果，包括：
    - 基础信息（接口 ID、名称、UID 等）
    - 请求信息
    - 响应信息
    - 断言结果
    - 提取的变量

    Args:
        startTime: 开始时间
        starter: 启动器
        interface: 接口对象
        request_info: 请求信息
        response: 响应对象或错误字符串
        asserts: 断言结果
        case_result: 用例结果
        variables: 变量列表
        task_result: 任务结果

    Returns:
        Tuple[结果字典, 是否成功]
    """
    interface_base_info = {
        'startTime': startTime,
        'interfaceID': interface.id,
        'interfaceName': interface.interface_name,
        'interfaceUid': interface.uid,
        'interfaceDesc': interface.interface_desc,
        'starterId': starter.userId,
        'starterName': starter.username,
        'interfaceProjectId': interface.project_id,
        'interfaceModuleId': interface.module_id,
        'interfaceEnvId': interface.env_id,
        'request_info': request_info
    }

    if task_result:
        interface_base_info['interface_task_result_Id'] = task_result.id
    if case_result:
        interface_base_info['interface_case_result_Id'] = case_result.id

    response_info = {
        'extracts': variables or [],
        'asserts': asserts or [],
        'result': InterfaceAPIResultEnum.SUCCESS,
        'request_method': interface.interface_method.upper()
    }

    flag = True

    if isinstance(response, str):
        response_info.update({
            'response_status': 500,
            'response_txt': response,
            'result': InterfaceAPIResultEnum.ERROR
        })
        flag = False

    elif isinstance(response, httpx.Response):
        is_success = response.status_code == 200
        response_info.update({
            'result': InterfaceAPIResultEnum.SUCCESS if is_success else InterfaceAPIResultEnum.ERROR,
            'response_status': response.status_code,
            'response_txt': response.text,
            'response_head': dict(response.headers),
            'request_head': dict(response.request.headers),
            'useTime': round(response.elapsed.total_seconds() * 1000, 2)
        })
        flag = is_success

    if asserts:
        has_failed_assert = any(
            assert_item.get('result') is False
            for assert_item in asserts
        )
        if has_failed_assert:
            flag = False
            response_info['result'] = InterfaceAPIResultEnum.ERROR

    return {**interface_base_info, **response_info}, flag
