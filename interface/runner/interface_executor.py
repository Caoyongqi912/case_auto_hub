#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/20
# @Author : cyq
# @File : interface_executor
# @Software: PyCharm
# @Desc: 接口执行器

from typing import List, Tuple, Mapping, Any

from app.model.interface import InterfaceAPI
from app.model.base import Env
from app.model.interface.interfaceResultModel import (
    InterfaceCaseResult, InterfaceTaskResult
)
from interface.exec import ExecAsserts, ExecResponseExtract, ExecSafeScript, ExecDBScript
from interface.exec.execExtract import ExecResponseExtract
from app.mapper.project.dbConfigMapper import DbConfigMapper
from app.mapper.interface.interfaceVarsMapper import InterfaceVarsMapper
from enums import InterfaceExtractTargetVariablesEnum, InterfaceResponseStatusCodeEnum
from interface.runner.url_builder import UrlBuilder
from utils import GenerateTools, log


class InterfaceExecutor:
    """接口执行器"""
    
    def __init__(self, starter, variable_manager, sender):
        self.starter = starter
        self.variable_manager = variable_manager
        self.sender = sender
    
    async def execute(
        self,
        interface: InterfaceAPI,
        env: Env = None,
        case_result: InterfaceCaseResult = None,
        task_result: InterfaceTaskResult = None,
        temp_vars: List[dict[str, Any]] = None
    ) -> Tuple[Mapping[str, Any], bool]:
        """执行接口"""
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
        t = GenerateTools.getTime(1)
        
        await self.starter.send(f"✍️✍️  EXECUTE API : {interface} ")
        try:
            url = await UrlBuilder.build(interface, env)
            
            await self._exec_before_params(interface.before_params)
            await self._exec_script(interface.before_script)
            await self._exec_before_sql(interface)
            
            request_info = await self.sender.set_req_info(interface)
            resolved_url = await self.variable_manager.trans(url)
            
            response = await self.sender(url=resolved_url, method=interface.method, **request_info)
            
            asserts_info = await self._exec_assert(response=response, interface=interface)
            temp_variables.extend(await self._exec_extract(response=response, interface=interface))
            temp_variables.extend(await self._exec_script(interface.after_script))
            
        except Exception as e:
            log.exception(e)
            await self.starter.send(f"Error occurred: \"{str(e)}\"")
            response = f"{str(e)} to {url}"
        finally:
            request_info['url'] = url
            from interface.writer import InterfaceAPIWriter
            return await InterfaceAPIWriter.set_interface_result_info(
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
    
    async def _exec_script(self, script: str):
        """执行脚本"""
        if script:
            exe = ExecSafeScript()
            _extracted_vars = exe.execute(script)
            await self.variable_manager.add_vars(_extracted_vars)
            await self.starter.send(f"🫳🫳  脚本 = {_extracted_vars}")
            return [{
                "key": k,
                "value": v,
                "target": "script"
            } for k, v in _extracted_vars.items()]
        return []
    
    async def _exec_before_params(self, before_params: List[Mapping[str, Any]] = None):
        """处理前置参数"""
        if before_params:
            values = await self.variable_manager.trans(before_params)
            log.debug(f"before params {values}")
            await self.variable_manager.add_vars(values)
            return [
                {
                    **item,
                    "target": "before_params"
                }
                for item in values
            ]
        return []
    
    async def _exec_before_sql(self, interface: InterfaceAPI):
        """执行前置SQL"""
        if not interface.before_sql or not interface.before_db_id:
            return []
        
        _db = await DbConfigMapper.get_by_id(interface.before_db_id)
        if not _db:
            log.warning(f"未找到数据库配置 ID: {interface.before_db_id}")
            return []
        
        script = await self.variable_manager.trans(interface.before_sql.strip())
        db_script = ExecDBScript(self.starter, script, interface.before_sql_extracts)
        res = await db_script.invoke(_db.db_type, **_db.config)
        await self.variable_manager.add_vars(res)
        await self.starter.send(f"🫳🫳    数据库读取 = {res}")
        
        if res:
            return [
                {
                    "key": k,
                    "value": v,
                    "target": "before_sql"
                }
                for k, v in res.items()
            ]
        return []
    
    async def _exec_assert(self, response, interface: InterfaceAPI):
        """响应断言"""
        _assert = ExecAsserts(response, self.variable_manager.get_vars())
        asserts_info = await _assert(interface.asserts)
        if asserts_info:
            await self.starter.send(f"🫳🫳  响应断言 = {asserts_info}")
        else:
            await self.starter.send(f"🫳🫳  未配置 响应断言 ⚠️⚠️")
        return asserts_info
    
    async def _exec_extract(self, response, interface: InterfaceAPI):
        """变量提取"""
        if interface.extracts and response.status_code == InterfaceResponseStatusCodeEnum.SUCCESS:
            _extract = ExecResponseExtract(response=response)
            _interface_extract = interface.extracts
            _vars = await _extract(_interface_extract)
            await self.starter.send(f"🫳🫳  响应参数提取 = {[{v.get('key'): v.get('value')} for v in _vars]}")
            await self.variable_manager.add_vars(_vars)
            return _vars
        return []
