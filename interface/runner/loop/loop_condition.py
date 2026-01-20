#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/20
# @Author : cyq
# @File : loop_condition
# @Software: PyCharm
# @Desc: 条件循环执行器

import asyncio

from app.model.interface import InterfaceAPI
from app.model.base import Env
from app.model.interface.InterfaceCaseStepContent import InterfaceCaseStepContent
from app.model.interface.interfaceResultModel import InterfaceContentResult
from utils.assertsUtil import MyAsserts
from utils import log
from .base import LoopExecutor
from interface.writer import InterfaceAPIWriter


class LoopConditionExecutor(LoopExecutor):
    """条件循环执行器"""
    
    async def execute(
        self,
        loop: InterfaceCaseStepContent,
        api_steps: list[InterfaceAPI],
        env: Env,
        content_result: InterfaceContentResult
    ):
        """
        条件循环
        
        key: str  'abc' '{{name}}'
        value: str 1
        operator: int
        """
        from interface.exec.execCondition import ExecCondition
        
        _execCondition = ExecCondition(self.variable_manager.vars)
        n = 0
        LOOP_SUCCESS = True
        
        while True:
            n += 1
            
            for index, interface in enumerate(api_steps, start=1):
                await self.starter.send(
                    f"✍️✍️  {'-' * 20} 执行循环步骤  {n} times: "
                    f"{interface.name} {'-' * 20}"
                )
                
                result, api_success = await self.interface_executor.execute(
                    interface=interface, env=env
                )
                
                if api_success is False:
                    LOOP_SUCCESS = False
                
                await InterfaceAPIWriter.write_interface_result(
                    interface_loop_result_id=content_result.id,
                    **result
                )
                
                if loop.loop_interval > 0:
                    LOOP_SUCCESS = False
                    await asyncio.sleep(loop.loop_interval)
            
            key = await self.variable_manager.trans(loop.key)
            value = await self.variable_manager.trans(loop.value)
            
            log.info(f"__loop_condition  key = {key}")
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
