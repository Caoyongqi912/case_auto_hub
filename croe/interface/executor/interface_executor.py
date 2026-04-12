#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Interface Executor

接口执行器
负责执行接口请求、处理前置/后置逻辑、断言验证和变量提取
"""
import copy
import json
from typing import Union, Tuple, Any, Dict, List, Optional

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
from croe.play.starter import UIStarter
from enums import ExtractTargetVariablesEnum, InterfaceAPIResultEnum, InterfaceResponseStatusCodeEnum
from utils import GenerateTools, log
from utils.execDBScript import ExecDBScript


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

    # ==================== 公共接口 ====================

    async def request_info(self, request_id: int, use_var: bool = False) -> Dict[str, Any]:
        """
        获取请求信息（用于调试）

        Args:
            request_id: 请求 ID
            use_var: 是否使用变量

        Returns:
            请求信息字典
        """
        interface = await InterfaceMapper.get_by_id(ident=request_id)
        host, url = await self._parse_url(interface)

        # 如果需要变量处理，执行前置逻辑
        if use_var:
            await self._execute_before_handlers(interface)
            url = await self.variable_manager.trans(target=url)

        # 构建请求信息
        request_info = await self._build_request_info(interface)
        
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
        temp_var: Optional[Dict] = None
    ) -> Tuple[Dict[str, Any], bool]:
        """
        执行接口请求（主入口）

        执行流程：
        1. 初始化临时变量
        2. 执行前置处理（参数、脚本、SQL）
        3. 构建并发送 HTTP 请求
        4. 执行变量提取
        5. 执行响应断言
        6. 构建并返回结果

        Args:
            interface: 接口对象
            env: 环境配置
            case_result: 用例结果
            task_result: 任务结果
            temp_var: 临时变量

        Returns:
            Tuple[接口结果信息字典, 是否执行成功]
        """
        # 初始化
        start_time = GenerateTools.getTime(1)
        temp_variables = self._normalize_temp_variables(temp_var)
        
        await self.starter.send(f"✍️✍️  EXECUTE API : {interface}")

        # 初始化结果变量
        resolved_url = ""
        response = None
        asserts_info = None

        try:
            # 构建并发送请求
            resolved_url = await self._build_and_send_request(interface, env, temp_variables)
            
            # 执行后置处理（提取和断言）
            response, asserts_info = await self._execute_post_handlers(interface, self._response)

        except Exception as e:
            # 异常处理
            log.exception(e)
            await self.starter.send(f"Error occurred: \"{str(e)}\"")
            response = f"{str(e)} to {resolved_url}"

        finally:
            # 构建并返回结果
            self._request_info['url'] = resolved_url
            return await self._build_result(
                start_time=start_time,
                interface=interface,
                request_info=self._request_info,
                response=response,
                env=env,
                asserts=asserts_info,
                case_result=case_result,
                task_result=task_result,
                variables=temp_variables
            )

    # ==================== 私有方法 - 请求构建 ====================

    async def _parse_url(self, interface: Interface) -> Tuple[str, str]:
        """
        解析 URL，返回 host 和 url

        Args:
            interface: 接口对象

        Returns:
            Tuple[host, url]
        """
        if interface.interface_env_id == UrlBuilder.CUSTOM_ENV_ID:
            # 自定义环境
            from utils import Tools
            parse = Tools.parse_url(interface.interface_url)
            url = parse.path
            host = f"{parse.scheme}://{parse.netloc}"
        else:
            # 使用环境配置
            env = await EnvMapper.get_by_id(ident=interface.interface_env_id)
            host = env.host
            url = interface.interface_url
            if env.port:
                host += f":{env.port}"
        
        return host, url

    async def _build_request_info(self, interface: Interface) -> Dict[str, Any]:
        """
        构建请求信息

        Args:
            interface: 接口对象

        Returns:
            请求信息字典
        """
        builder = RequestBuilder(self.variable_manager)
        request_info = await builder.set_req_info(interface)
        
        # 移除不需要的字段
        request_info.pop("follow_redirects", None)
        request_info.pop("read", None)
        request_info.pop("connect", None)
        
        return request_info

    async def _build_and_send_request(
        self,
        interface: Interface,
        env: Optional[EnvModel],
        temp_variables: List
    ) -> str:
        """
        构建并发送 HTTP 请求

        Args:
            interface: 接口对象
            env: 环境配置
            temp_variables: 临时变量列表（会被修改）

        Returns:
            解析后的 URL
        """
        # 构建原始 URL
        origin_url = await UrlBuilder.build(interface=interface, env=env)
        
        # 执行前置处理
        temp_variables.extend(await self._execute_before_handlers(interface))
        
        # 构建请求信息
        builder = RequestBuilder(self.variable_manager)
        self._request_info = await builder.set_req_info(interface)
        
        # 变量替换
        resolved_url = await self.variable_manager.trans(origin_url)
        
        # 发送请求
        self._response = await self.http(
            url=resolved_url,
            method=interface.interface_method,
            **self._request_info
        )
        
        return resolved_url

    # ==================== 私有方法 - 前置处理 ====================

    async def _execute_before_handlers(self, interface: Interface) -> List:
        """
        执行所有前置处理器

        按顺序执行：前置参数 -> 前置脚本 -> 前置 SQL

        Args:
            interface: 接口对象

        Returns:
            提取的变量列表
        """
        variables = []
        variables.extend(await self._execute_before_params(interface.interface_before_params))
        variables.extend(await self._execute_before_script(interface.interface_before_script))
        variables.extend(await self._execute_before_sql(interface))
        return variables

    async def _execute_before_params(self, before_params: Optional[List[Dict]] = None) -> List:
        """
        执行前置参数处理

        Args:
            before_params: 前置参数列表

        Returns:
            处理后的变量列表
        """
        if not before_params:
            return []

        # 变量替换
        values = await self.variable_manager.trans(before_params)
        log.info(f"执行前参数处理: {values}")

        if not values:
            return []

        # 添加到变量管理器
        await self.variable_manager.add_vars(values)
        
        # 标记变量来源
        return [
            {**item, ExtractTargetVariablesEnum.Target: ExtractTargetVariablesEnum.BeforeParams}
            for item in values
        ]

    async def _execute_before_script(self, script: Optional[str]) -> List:
        """
        执行前置脚本处理

        Args:
            script: 脚本内容

        Returns:
            提取的变量列表
        """
        if not script:
            return []

        # 执行脚本
        script_manager = ScriptManager()
        extracted_vars = script_manager.execute(script)
        
        # 添加到变量管理器
        await self.variable_manager.add_vars(extracted_vars)
        await self.starter.send(f"🫳🫳  脚本 = {json.dumps(extracted_vars, ensure_ascii=False)}")
        
        # 标记变量来源
        return [
            {
                ExtractTargetVariablesEnum.KEY: k,
                ExtractTargetVariablesEnum.VALUE: v,
                ExtractTargetVariablesEnum.Target: ExtractTargetVariablesEnum.BeforeScript
            }
            for k, v in extracted_vars.items()
        ]

    async def _execute_before_sql(self, interface: Interface) -> List:
        """
        执行前置 SQL 处理

        Args:
            interface: 接口对象

        Returns:
            提取的变量列表
        """
        # 检查是否配置了前置 SQL
        if not interface.interface_before_sql or not interface.interface_before_db_id:
            return []

        # 获取数据库配置
        db_config = await DbConfigMapper.get_by_id(interface.interface_before_db_id)
        if not db_config:
            await self.starter.send(f"数据库配置不存在，db_id = {interface.interface_before_db_id}")
            return []

        # 变量替换
        db_script = await self.variable_manager.trans(interface.interface_before_sql.strip())
        log.info(f"执行前sql处理: {db_script}")

        # 执行 SQL
        db_executor = ExecDBScript(
            self.starter,
            db_script,
            interface.interface_before_sql_extracts
        )
        result = await db_executor.invoke(db_config.db_type, **db_config.config)

        # 添加到变量管理器
        await self.variable_manager.add_vars(result)
        await self.starter.send(f"🫳🫳    数据库读取 = {result}")

        if not result:
            return []

        # 标记变量来源
        return [
            {
                ExtractTargetVariablesEnum.KEY: k,
                ExtractTargetVariablesEnum.VALUE: v,
                ExtractTargetVariablesEnum.Target: ExtractTargetVariablesEnum.BeforeSQL
            }
            for k, v in result.items()
        ]

    # ==================== 私有方法 - 后置处理 ====================

    async def _execute_post_handlers(
        self,
        interface: Interface,
        response: httpx.Response
    ) -> Tuple[httpx.Response, Optional[List]]:
        """
        执行所有后置处理器

        按顺序执行：变量提取 -> 响应断言

        Args:
            interface: 接口对象
            response: HTTP 响应对象

        Returns:
            Tuple[响应对象, 断言结果]
        """
        # 变量提取
        self._extracted_vars = await self._execute_extract(response, interface)
        
        # 响应断言
        asserts_info = await self._execute_assert(response, interface)
        
        return response, asserts_info

    async def _execute_assert(
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
            await self.starter.send(f"🫳🫳  响应断言 = {json.dumps(asserts_info, ensure_ascii=False)}")
        else:
            await self.starter.send(f"🫳🫳  未配置 响应断言 ⚠️⚠️")

        return asserts_info

    async def _execute_extract(
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
        # 检查是否需要提取变量
        if not interface.interface_extracts:
            return []

        # 检查响应状态码
        if response.status_code != InterfaceResponseStatusCodeEnum.SUCCESS:
            return []

        # 执行提取
        extract_manager = ExtractManager(response=response)
        interface_extracts = copy.deepcopy(interface.interface_extracts)
        vars_list = await extract_manager(interface_extracts)

        # 记录日志
        await self.starter.send(
            f"🫳🫳  响应参数提取 = {[{v.get('key'): v.get('value')} for v in vars_list]}"
        )
        
        # 添加到变量管理器
        await self.variable_manager.add_vars(vars_list)
        
        return vars_list

    # ==================== 私有方法 - 结果构建 ====================

    async def _build_result(
        self,
        start_time: str,
        interface: Interface,
        request_info: Dict[str, Any],
        response: Union[httpx.Response, str],
        env: Optional[EnvModel],
        asserts: Optional[List],
        case_result: Optional[Any],
        task_result: Optional[Any],
        variables: List
    ) -> Tuple[Dict[str, Any], bool]:
        """
        构建接口执行结果

        Args:
            start_time: 开始时间
            interface: 接口对象
            request_info: 请求信息
            response: 响应对象或错误字符串
            env: 环境配置
            asserts: 断言结果
            case_result: 用例结果
            task_result: 任务结果
            variables: 变量列表

        Returns:
            Tuple[结果字典, 是否成功]
        """
        # 构建基础信息
        result = self._build_base_info(start_time, interface, request_info, env)
        
        # 添加关联信息
        if task_result:
            result['interface_task_result_Id'] = task_result.id
        if case_result:
            result['interface_case_result_Id'] = case_result.id

        # 构建响应信息
        response_info, flag = self._build_response_info(response, interface, asserts, variables)
        
        # 合并结果
        result.update(response_info)
        
        return result, flag

    def _build_base_info(
        self,
        start_time: str,
        interface: Interface,
        request_info: Dict[str, Any],
        env: Optional[EnvModel]
    ) -> Dict[str, Any]:
        """
        构建基础信息

        Args:
            start_time: 开始时间
            interface: 接口对象
            request_info: 请求信息
            env: 环境配置

        Returns:
            基础信息字典
        """
        base_info = {
            'start_time': start_time,
            'interface_id': interface.id,
            'interface_name': interface.interface_name,
            'interface_uid': interface.uid,
            'interface_desc': interface.interface_desc,
            'starter_id': self.starter.userId,
            'starter_name': self.starter.username,
            'request_url': request_info.get('url'),
            'request_method': request_info.get('method'),
            'request_params': request_info.get('params') or {},
            'request_body': request_info.get('body') or {},
            'request_head': request_info.get('headers') or {},
        }

        # 添加环境信息
        if env:
            base_info['running_env_id'] = env.id
            base_info['running_env_name'] = env.env_name
        else:
            base_info['running_env_id'] = interface.env_id
            base_info['running_env_name'] = interface.env_name

        return base_info

    def _build_response_info(
        self,
        response: Union[httpx.Response, str],
        interface: Interface,
        asserts: Optional[List],
        variables: List
    ) -> Tuple[Dict[str, Any], bool]:
        """
        构建响应信息

        Args:
            response: 响应对象或错误字符串
            interface: 接口对象
            asserts: 断言结果
            variables: 变量列表

        Returns:
            Tuple[响应信息字典, 是否成功]
        """
        response_info = {
            'extracts': variables or [],
            'asserts': asserts or [],
            'result': InterfaceAPIResultEnum.SUCCESS,
            'request_method': interface.interface_method.upper()
        }

        flag = True

        # 处理异常响应
        if isinstance(response, str):
            response_info.update({
                'response_status': 500,
                'response_txt': response,
                'result': InterfaceAPIResultEnum.ERROR
            })
            flag = False

        # 处理正常响应
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

        # 检查断言结果
        if asserts:
            has_failed_assert = any(
                assert_item.get('result') is False
                for assert_item in asserts
            )
            if has_failed_assert:
                flag = False
                response_info['result'] = InterfaceAPIResultEnum.ERROR

        return response_info, flag

    # ==================== 私有方法 - 工具方法 ====================

    def _normalize_temp_variables(self, temp_var: Optional[Union[Dict, List]]) -> List:
        """
        标准化临时变量

        将单个变量或变量列表统一转换为列表格式

        Args:
            temp_var: 临时变量（单个或列表）

        Returns:
            变量列表
        """
        if not temp_var:
            return []

        if isinstance(temp_var, list):
            return temp_var
        
        return [temp_var]
