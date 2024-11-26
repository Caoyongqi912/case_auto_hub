#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/19# @Author : cyq# @File : runner# @Software: PyCharm# @Desc:from typing import List, Dict, Anyimport httpxfrom httpx import Response, ConnectErrorfrom app.model.base import Userfrom app.model.interface import InterfaceModelfrom utils import MyLoguru, GenerateToolsfrom app.mapper.interface import InterfaceMapper, InterfaceCaseMapperfrom .execScript import ExecScriptForInterfacefrom .sender import Senderfrom .writer import InterfaceAPIWriterclass InterFaceRunner:    response: Response = None    def __init__(self, starter: User):        self.starter = starter        self.variables = {}        self.log = MyLoguru().get_logger()        self.sender = Sender(self.variables, self.log)    async def set_variables(self, data: Dict[str, Any] | List[Dict[str, Any]]):        """        设置变量        :param data:        :return:        """        if isinstance(data, dict):            self.variables.update(**data)        elif isinstance(data, list):            _ = await GenerateTools.list2dict(data)            self.variables.update(**_)    async def try_interface(self, interfaceId: int):        """        执行单个接口请求调试        无变量、有前置方法、        需要返回response        """        interface = await InterfaceMapper.get_by_id(ident=interfaceId)        return await self.__execute_interface(interface, no_db=True)    async def run_interCase(self, caseId: int):        """        执行接口用例        """        interfaces = await InterfaceCaseMapper.query_interface_by_caseId(caseId=caseId)        for index, interface in enumerate(interfaces, start=1):            self.log.info(f"step {index} : {interfaces}")            response = await self.__execute_interface(interface)            return    async def __execute_interface(self,                                  interface: InterfaceModel,                                  no_db: bool = False):        """        API 执行        """        try:            # 1、前置变量参数            await self.__exec_before_params(interface.beforeParams)            # 2、执行前置函数            bs = await self.__exec_before_script(interface.beforeScript)            self.variables.update(**bs)            # 3、执行接口请求            self.response = await self.sender(interface)            # 4、进行断言            assertInfo = await self.__exec_assert(interface)            # 5、出参提取            extractInfo = await self.__exec_extract(interface)            # 6、执行后置函数            await self.__exec_after_script(interface.afterScript)            return await InterfaceAPIWriter.writer_interface_result(                no_db=no_db,                starter=self.starter,                interface=interface,                response=self.response,                variables=self.variables)        except ConnectError as e:            self.log.error(e)            return f"{str(e)} to {interface.url}"        except Exception as e:            self.log.error(e)            return f"{str(e)}"    async def __exec_before_script(self, script: str):        if script:            exe = ExecScriptForInterface(funcStr=script, variables=self.variables, log=self.log)            return exe.exec_beforeFunc()        return {}    async def __exec_before_params(self, before_params: List[Dict[str, Any]] = None):        """处理前置参数"""        if before_params:            await self.set_variables(before_params)    async def __exec_after_script(self, script: str):        ...    async def __exec_assert(self, interface: InterfaceModel):        if not interface.asserts:            return    async def __exec_extract(self, interface: InterfaceModel):        if not interface.extracts:            return