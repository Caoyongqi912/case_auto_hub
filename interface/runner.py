#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/19# @Author : cyq# @File : runner# @Software: PyCharm# @Desc:import asynciofrom typing import List, Dict, Any, Mappingfrom httpx import Responsefrom app.mapper.project.env import EnvMapperfrom app.model.base import Userfrom app.model.interface import InterfaceModel, InterfaceCaseResultModelfrom enums import InterfaceExtractTargetVariablesEnum, InterfaceResponseStatusCodeEnum, InterfaceAPIResultEnumfrom utils import MyLoguru, GenerateToolsfrom app.mapper.interface import InterfaceMapper, InterfaceCaseMapperfrom .execAssert import ExecAssertsfrom .execExtract import ExecResponseExtractfrom .execScript import ExecScriptForInterfacefrom .sender import HttpSenderfrom .io_sender import APISocketSenderfrom .writer import InterfaceAPIWriterlog = MyLoguru().get_logger()class InterFaceRunner:    response: Response = None    def __init__(self, starter: User, io: APISocketSender | None = None):        self.starter = starter        self.variables = {}        self.io = io        self.sender = HttpSender(self.variables, self.io)    async def set_variables(self, data: Dict[str, Any] | List[Dict[str, Any]]) -> Dict[str, Any]:        """        设置变量        :param data:        :return:        """        if isinstance(data, dict):            self.variables.update(**data)        elif isinstance(data, list):            data = await GenerateTools.list2dict(data)            self.variables.update(**data)        return data    async def try_interface(self, interfaceId: int):        """        执行单个接口请求调试        无变量、有前置方法、        需要返回response        """        interface = await InterfaceMapper.get_by_id(ident=interfaceId)        return await self.__execute_interface(interface, no_db=True)    async def run_interCase(self, caseId: int):        """        执行接口用例        """        interfaceCase = await InterfaceCaseMapper.get_by_id(ident=caseId)        await self.io.send(f"用例 {interfaceCase.title} 执行开始。执行人 {self.starter.username}")        interfaces = await InterfaceCaseMapper.query_interface_by_caseId(caseId=caseId)        await self.io.send(f"查询到关联API x {len(interfaces)} ...")        if len(interfaces) == 0:            return await self.io.over()        caseResult = await InterfaceAPIWriter.init_interface_case_result(interfaceCase=interfaceCase,                                                                         starter=self.starter)        await self.io.send(f"初始化结果模型 。。。 ✅ ID= '{caseResult.uid}'")        try:            for index, interface in enumerate(interfaces, start=1):                await self.io.send(f"execute Step {index} ： {interface}")                result = await self.__execute_interface(interface=interface, caseResult=caseResult)                if result['result'] == InterfaceResponseStatusCodeEnum.SUCCESS:                    caseResult.success_num += 1                else:                    caseResult.fail_num += 1                    caseResult.result = InterfaceAPIResultEnum.ERROR            return await InterfaceAPIWriter.finally_interface_case_result(caseResult=caseResult)        finally:            await self.io.over(caseResult.id)    async def __execute_interface(self,                                  interface: InterfaceModel,                                  caseResult: InterfaceCaseResultModel = None,                                  no_db: bool = False):        """        API 执行        """        # 0、接口处理请求URL        url = await self.set_req_url(interface)        try:            temp_variables = []            # 1、前置变量参数            temp_variables.extend(await self.__exec_before_params(interface.beforeParams))            # 2、执行前置函数            temp_variables.extend(await self.__exec_before_script(interface.beforeScript))            # 3、执行接口请求            self.response = await self.sender(url=url, interface=interface)            # 4、进行断言            asserts_info = await self.__exec_assert(interface)            # 5、出参提取            temp_variables.extend(await self.__exec_extract(interface))            # 6、执行后置函数            temp_variables.extend(await self.__exec_after_script(interface))            await self.io.send(f"temp variables: {temp_variables}")            return await InterfaceAPIWriter.writer_interface_result(                no_db=no_db,                starter=self.starter,                interface=interface,                response=self.response,                asserts=asserts_info,                caseResult=caseResult,                variables=temp_variables)        except Exception as e:            return await self._handle_error(                caseResult=caseResult,                no_db=no_db,                exception=e,                interface=interface,                to_url=url,                custom_message=str(e))    async def __exec_before_script(self, script: str) -> List[Any] | List[Mapping[str, Any]]:        """处理前置脚本"""        if script:            exe = ExecScriptForInterface(funcStr=script)            extracted_vars = await self.set_variables(exe.exec_script())            await self.io.send(f"前置脚本 = {extracted_vars}")            _vars = [                {                    InterfaceExtractTargetVariablesEnum.KEY: k,                    InterfaceExtractTargetVariablesEnum.VALUE: v,                    InterfaceExtractTargetVariablesEnum.Target: InterfaceExtractTargetVariablesEnum.BeforeScript                }                for k, v in extracted_vars.items()            ]            return _vars        return []    async def __exec_before_params(self, before_params: List[Dict[str, Any]] = None):        """处理前置参数"""        if before_params:            extracted_vars = await self.set_variables(before_params)            await self.io.send(f"前置参数 = {extracted_vars}")            _vars = [                {                    InterfaceExtractTargetVariablesEnum.KEY: k,                    InterfaceExtractTargetVariablesEnum.VALUE: v,                    InterfaceExtractTargetVariablesEnum.Target: InterfaceExtractTargetVariablesEnum.BeforeParams                }                for k, v in extracted_vars.items()            ]            return _vars        return []    async def __exec_assert(self, interface: InterfaceModel):        """        响应断言        前提：        1、有断言        2、有响应        3、响应200        """        if interface.asserts and self.response.status_code == InterfaceResponseStatusCodeEnum.SUCCESS:            _assert = ExecAsserts(self.response)            return await _assert(interface.asserts)    async def __exec_extract(self, interface: InterfaceModel):        """        变量提取        前提：        1、有断言        2、有响应        3、响应200        """        if interface.extracts and self.response.status_code == InterfaceResponseStatusCodeEnum.SUCCESS:            _extract = ExecResponseExtract(response=self.response)            _vars = await _extract(interface.extracts)            await self.io.send(f"响应参数提取 = {_vars}")            await self.set_variables(_vars)            return _vars        return []    async def __exec_after_script(self, interface: InterfaceModel):        """        执行后置脚本        """        if interface.afterScript and self.response.status_code == InterfaceResponseStatusCodeEnum.SUCCESS:            exe = ExecScriptForInterface(funcStr=interface.afterScript, response=self.response)            extracted_vars = await self.set_variables(exe.exec_script())            await self.io.send(f"前置脚本 = {extracted_vars}")            _vars = [                {                    InterfaceExtractTargetVariablesEnum.KEY: k,                    InterfaceExtractTargetVariablesEnum.VALUE: v,                    InterfaceExtractTargetVariablesEnum.Target: InterfaceExtractTargetVariablesEnum.AfterScript                }                for k, v in extracted_vars.items()            ]            return _vars        return []    async def set_req_url(self, interface: InterfaceModel):        env = await EnvMapper.get_by_id(ident=interface.env_id)        domain = env.host        if env.port:            domain += f":{env.port}"        await self.io.send(f"request url = '{domain + interface.url}'")        return domain + interface.url    async def _handle_error(self, no_db: bool,                            exception: Exception,                            interface: InterfaceModel,                            custom_message: str,                            to_url: str,                            caseResult: InterfaceCaseResultModel = None):        """        错误处理的辅助函数        """        # 记录错误日志        await self.io.send(f"Error occurred: {str(exception)}")        # 返回接口执行结果并记录错误        return await InterfaceAPIWriter.writer_interface_result(            caseResult=caseResult,            no_db=no_db,            starter=self.starter,            interface=interface,  # 可以传入适当的interface信息，视需要而定            response=f"{custom_message} to {to_url}"        )