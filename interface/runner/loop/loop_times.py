#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/20
# @Author : cyq
# @File : loop_times
# @Software: PyCharm
# @Desc: 次数循环执行器

import asyncio

from app.model.interface import InterfaceAPI
from app.model.base import Env
from app.model.interface.InterfaceCaseStepContent import InterfaceCaseStepContent
from app.model.interface.interfaceResultModel import InterfaceContentResult
from .base import LoopExecutor
from interface.writer import InterfaceAPIWriter


class LoopTimesExecutor(LoopExecutor):
    """次数循环执行器"""
    
    async def execute(
        self,
        loop: InterfaceCaseStepContent,
        api_steps: list[InterfaceAPI],
        env: Env,
        content_result: InterfaceContentResult
    ):
        """
        次数循环执行
        
        全部执行完，不论对错
        全对 content result = true
        case success +1
        """
        ALL_SUCCESS = True
        loop_times = loop.loop_times
        
        for i in range(loop_times):
            for index, interface in enumerate(api_steps, start=1):
                await self.starter.send(
                    f"✍️✍️  {'-' * 20} 次数循环步骤 次数{i}   {interface.name} {'-' * 20}"
                )
                result, api_success = await self.interface_executor.execute(
                    interface=interface, env=env
                )
                
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
