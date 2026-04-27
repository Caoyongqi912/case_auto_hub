#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Interface Executor

接口执行器
负责执行接口请求、处理前置/后置逻辑、断言验证和变量提取
"""
import copy
import json
from dataclasses import dataclass, field
from typing import Union, Tuple, Any, Dict, List, Optional

import httpx

from app.mapper.project.dbConfigMapper import DbConfigMapper
from app.mapper.project.env import EnvMapper
from app.model.base import EnvModel
from app.model.interfaceAPIModel.interfaceGlobalModel import InterfaceGlobalHeader
from app.model.interfaceAPIModel.interfaceModel import Interface
from common.httpxClient import HttpxClient
from croe.a_manager import ScriptManager, VariableManager
from croe.a_manager.assert_manager import AssertManager
from croe.interface.builder.request_builder import RequestBuilder
from croe.interface.builder.url_builder import UrlBuilder
from croe.interface.manager.extract_manager import ExtractManager
from croe.interface.starter import APIStarter
from croe.play.starter import UIStarter
from enums import ExtractTargetVariablesEnum, InterfaceResponseStatusCodeEnum
from utils import GenerateTools, log
from utils.execDBScript import ExecDBScript


@dataclass
class ExecutionContext:
    """
    执行上下文数据类

    封装接口执行过程中的所有状态信息，避免方法参数过多和隐式状态共享
    """
    interface: Interface
    env: Optional[EnvModel] = None
    start_time: str = ""
    resolved_url: str = ""
    response: Optional[httpx.Response] = None
    error: Optional[str] = None
    request_info: Dict[str, Any] = field(default_factory=dict)
    variables: List = field(default_factory=list)
    extracted_vars: List = field(default_factory=list)
    asserts: Optional[List] = None
    success: bool = True


class InterfaceExecutor:
    """
    接口执行器

    负责执行单个接口请求，包括：
    - 构建和执行 HTTP 请求
    - 处理前置参数、脚本和 SQL
    - 执行响应断言
    - 提取变量
    """

    def __init__(self, starter: Union[UIStarter, APIStarter],
                 variable_manager: VariableManager,
                 global_headers:List[InterfaceGlobalHeader]=None,
                 ):
        """
        初始化接口执行器

        Args:
            starter: 启动器（UI 或 API），用于日志输出
            variable_manager: 变量管理器，用于变量替换和存储
        """
        self.variable_manager: VariableManager = variable_manager
        self.starter: Union[UIStarter, APIStarter] = starter
        self.http: HttpxClient = HttpxClient(logger=self.starter.send)
        self.g_headers: List[InterfaceGlobalHeader] = global_headers or []

    async def execute(
        self,
        interface: Interface,
        env: Optional[EnvModel] = None,
        temp_var: Optional[Dict] = None
    ) -> Tuple[Dict[str, Any], bool]:
        """
        执行接口请求（主入口）

        执行流程：
        1. 初始化执行上下文
        2. 构建并发送 HTTP 请求
        3. 执行后置处理（变量提取 + 断言）
        4. 构建并返回结果

        Args:
            interface: 接口对象
            env: 环境配置
            temp_var: 临时变量（单个 dict 或 list）

        Returns:
            Tuple[结果字典, 是否成功]
            结果字典字段与 InterfaceResult 模型对齐
        """
        # 创建执行上下文
        ctx: ExecutionContext = ExecutionContext(
            interface=interface,
            env=env,
            start_time=GenerateTools.getTime(1),
        )
        # 标准化临时变量
        ctx.variables = self._normalize_temp_variables(temp_var)

        # 输出执行日志
        await self.starter.send(f"✍️✍️  EXECUTE API : {interface}")

        try:
            # 构建并发送请求
            await self._build_and_send_request(ctx)
            # 执行后置处理
            await self._execute_post_handlers(ctx)
        except Exception as e:
            # 捕获所有异常并记录
            log.exception(e)
            ctx.error = str(e)
            await self.starter.send(f"Error occurred: \"{str(e)}\"")

        # 构建并返回结果
        return self._build_result(ctx)

    @staticmethod
    async def _parse_url(interface: Interface) -> Tuple[str, str]:
        """
        解析 URL，返回 host 和 path

        Args:
            interface: 接口对象

        Returns:
            Tuple[host, url_path]
        """
        # 判断是否使用自定义环境
        if interface.env_id == UrlBuilder.CUSTOM_ENV_ID:
            # 自定义环境：从接口 URL 中解析 host 和 path
            from utils import Tools
            parse = Tools.parse_url(interface.interface_url)
            url = parse.path
            host = f"{parse.scheme}://{parse.netloc}"
        else:
            # 使用预配置环境
            env = await EnvMapper.get_by_id(ident=interface.env_id)
            host = env.host
            url = interface.interface_url
            if env.port:
                host += f":{env.port}"

        return host, url

    async def _build_and_send_request(self, ctx: ExecutionContext) -> None:
        """
        构建并发送 HTTP 请求

        Args:
            ctx: 执行上下文
        """
        # 构建原始 URL
        origin_url = await UrlBuilder.build(interface=ctx.interface, env=ctx.env)
        log.info(f"origin_url = {origin_url}")
        # 执行前置处理器，扩展变量列表
        ctx.variables.extend(await self._execute_before_handlers(ctx.interface))

        # 构建请求信息（headers, body, params 等）
        builder = RequestBuilder(self.variable_manager, self.g_headers)
        ctx.request_info = await builder.set_req_info(ctx.interface)

        # 变量替换
        ctx.resolved_url = await self.variable_manager.trans(origin_url)
        log.info(f"resolved_url = {ctx.resolved_url}")
        ctx.request_info['url'] = ctx.resolved_url

        # 发送 HTTP 请求
        ctx.response = await self.http(
            method=ctx.interface.interface_method,
            **ctx.request_info
        )

    async def _execute_before_handlers(self, interface: Interface) -> List[Dict]:
        """
        执行所有前置处理器

        按顺序执行：
        1. 前置参数处理
        2. 前置脚本处理
        3. 前置 SQL 处理

        Args:
            interface: 接口对象

        Returns:
            提取的变量列表
        """
        variables: List = []
        # 执行前置参数
        variables.extend(await self._execute_before_params(interface.interface_before_params))
        # 执行前置脚本
        variables.extend(await self._execute_before_script(interface.interface_before_script))
        # 执行前置 SQL
        variables.extend(await self._execute_before_sql(interface))
        return variables

    async def _execute_before_params(self, before_params: Optional[List[Dict]] = None) -> List[Dict]:
        """
        执行前置参数处理

        对配置的参数进行变量替换后存入变量管理器

        Args:
            before_params: 前置参数列表

        Returns:
            处理后的变量列表（标记来源为 BeforeParams）
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

    async def _execute_before_script(self, script: Optional[str]) -> List[Dict]:
        """
        执行前置脚本处理

        执行用户自定义脚本，从输出中提取变量

        Args:
            script: 脚本内容

        Returns:
            提取的变量列表（标记来源为 BeforeScript）
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

    async def _execute_before_sql(self, interface: Interface) -> List[Dict]:
        """
        执行前置 SQL 处理

        执行预置 SQL 查询，从结果中提取变量

        Args:
            interface: 接口对象

        Returns:
            提取的变量列表（标记来源为 BeforeSQL）
        """
        # 检查是否配置了前置 SQL
        if not interface.interface_before_sql or not interface.interface_before_db_id:
            return []

        # 获取数据库配置
        db_config = await DbConfigMapper.get_by_id(interface.interface_before_db_id)
        if not db_config:
            await self.starter.send(f"数据库配置不存在，db_id = {interface.interface_before_db_id}")
            return []

        # 变量替换 SQL 语句
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

    async def _execute_post_handlers(self, ctx: ExecutionContext) -> None:
        """
        执行所有后置处理器

        包括：
        1. 变量提取
        2. 响应断言

        Args:
            ctx: 执行上下文
        """
        if not ctx.response:
            return

        # 执行变量提取
        ctx.extracted_vars = await self._execute_extract(ctx.response, ctx.interface)
        # 执行响应断言
        ctx.asserts = await self._execute_assert(ctx.response, ctx.interface)

    async def _execute_assert(
        self,
        response: httpx.Response,
        interface: Interface
    ) -> Optional[List[Dict]]:
        """
        执行响应断言

        Args:
            response: HTTP 响应对象
            interface: 接口对象

        Returns:
            断言结果列表
        """
        # 创建断言管理器
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
    ) -> List[Dict]:
        """
        执行变量提取

        从 HTTP 响应中根据配置提取变量

        Args:
            response: HTTP 响应对象
            interface: 接口对象

        Returns:
            提取的变量列表
        """
        # 检查是否配置了提取规则
        if not interface.interface_extracts:
            return []

        # 非 200 状态码不进行提取
        if response.status_code != InterfaceResponseStatusCodeEnum.SUCCESS:
            return []

        # 执行提取
        extract_manager = ExtractManager(response=response)
        interface_extracts = copy.deepcopy(interface.interface_extracts)
        vars_list = await extract_manager(interface_extracts)

        # 输出日志
        await self.starter.send(
            f"🫳🫳  响应参数提取 = {[{v.get('key'): v.get('value')} for v in vars_list]}"
        )

        # 添加到变量管理器
        await self.variable_manager.add_vars(vars_list)

        return vars_list

    def _build_result(self, ctx: ExecutionContext) -> Tuple[Dict[str, Any], bool]:
        """
        构建接口执行结果

        构建结果与 InterfaceResult 模型字段对齐

        Args:
            ctx: 执行上下文

        Returns:
            Tuple[结果字典, 是否成功]
        """
        # 基础信息
        result: Dict[str, Any] = {
            'interface_id': ctx.interface.id,
            'interface_name': ctx.interface.interface_name,
            'interface_uid': ctx.interface.uid,
            'interface_desc': ctx.interface.interface_desc,
            'starter_id': self.starter.userId,
            'starter_name': self.starter.username,
            'request_url': ctx.resolved_url,
            'request_method': ctx.interface.interface_method,
            'request_params': ctx.request_info.get('params') or None,
            "request_body_type": ctx.interface.interface_body_type,
            'request_json': json.dumps(ctx.request_info.get('json')) if ctx.request_info.get('json') else None,
            'request_data': json.dumps(ctx.request_info.get('data')) if ctx.request_info.get('data') else None,
            'request_headers': ctx.request_info.get('headers') or None,
            'extracts': ctx.extracted_vars or [],
            'asserts': ctx.asserts or [],
        }

        # 环境信息
        if ctx.env:
            result['running_env_id'] = ctx.env.id
            result['running_env_name'] = ctx.env.name
        else:
            result['running_env_id'] = ctx.interface.env_id

        # 错误处理
        if ctx.error:
            result.update({
                'response_status': 500,
                'response_text': ctx.error,
                'result': False,
                'use_time': '0'
            })
            ctx.success = False
        # 正常响应处理
        elif isinstance(ctx.response, httpx.Response):
            is_success = ctx.response.status_code == 200
            result.update({
                'response_status': ctx.response.status_code,
                'response_text': ctx.response.text,
                'response_headers': {k: v for k, v in ctx.response.headers.items()},
                'use_time': str(round(ctx.response.elapsed.total_seconds() * 1000, 2))
            })
            if not is_success:
                ctx.success = False

        # 检查断言结果
        if ctx.asserts:
            has_failed = any(a.get('result') is False for a in ctx.asserts)
            if has_failed:
                ctx.success = False

        result['result'] = ctx.success
        result['start_time'] = ctx.start_time

        return result, ctx.success

    @staticmethod
    def _normalize_temp_variables(temp_var: Optional[Union[Dict, List]]) -> List:
        """
        标准化临时变量

        将单个变量 dict 或变量列表统一转换为 list 格式

        Args:
            temp_var: 临时变量（单个 dict 或 list）

        Returns:
            变量列表
        """
        if not temp_var:
            return []
        if isinstance(temp_var, list):
            return temp_var
        return [temp_var]
