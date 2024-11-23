#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/19# @Author : cyq# @File : runner# @Software: PyCharm# @Desc:from httpx import Response, ConnectErrorfrom app.controller.ui.ui_task import startfrom app.model.interface import InterfaceModelfrom utils import MyLogurufrom app.mapper.interface import InterfaceMapper, InterfaceCaseMapperfrom .sender import Senderclass InterFaceRunner:    def __init__(self):        self.variables = {}        self.sender = Sender()        self.log = MyLoguru().get_logger()    async def try_interface(self, interfaceId: int):        """        执行单个接口请求调试        无变量、有前置方法、        需要返回response        """        interface = await InterfaceMapper.get_by_id(ident=interfaceId)        self.log.info(interface)        response = await self.__execute_interface(interface)        return response    async def run_interCase(self, caseId: int):        """        执行接口用例        """        interfaces = await InterfaceCaseMapper.query_interface_by_caseId(caseId=caseId)        for index, interface in enumerate(interfaces, start=1):            self.log.info(f"step {index} : {interfaces}")            response = await self.__execute_interface(interface)            return    async def run_interTask(self, taskId: int):        pass    async def __execute_interface(self, interface: InterfaceModel):        """        单用例执行        """        # 1、前置变量参数        await self.__exec_before_params(interface.beforeParams)        # 2、执行前置函数        await self.__exec_before_script(interface.beforeScript)        # 3、执行接口请求        try:            response = await self.sender(interface)        except ConnectError as e:            return "connect error"        # 4、进行断言        assertInfo = await self.__exec_assert(response, interface)        # 5、出参提取        extractInfo = await self.__exec_extract(response, interface)        # 6、执行后置函数        await self.__exec_after_script(response, interface.afterScript)        return "ok"    async def __exec_before_script(self, script: str):        ...    async def __exec_before_params(self, *args, **kwargs):        if kwargs:            await self.set_variables(**kwargs)    async def __exec_after_script(self, response: Response, script: str):        ...    async def __exec_assert(self, response: Response, interface: InterfaceModel):        if not interface.asserts:            return    async def __exec_extract(self, response: Response, interface: InterfaceModel):        if not interface.extracts:            return    async def set_variables(self, **kwargs):        self.variables.update(**kwargs)