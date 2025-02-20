#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/19# @Author : cyq# @File : runner# @Software: PyCharm# @Desc:from typing import List, Dict, Any, Mapping, TypeVar, Tuplefrom httpx import Responsefrom app.mapper.interface.interfaceGroupMapper import InterfaceGroupMapperfrom app.mapper.interface.interfaceVarsMapper import InterfaceVarsMapperfrom app.mapper.project.dbConfigMapper import DbConfigMapperfrom app.mapper.project.env import EnvMapperfrom app.model.interface import InterfaceModel, InterfaceCaseResultModel, InterFaceCaseModel, InterfaceTask, \    InterfaceTaskResultModel, InterfaceVariablesfrom enums import InterfaceExtractTargetVariablesEnum, InterfaceResponseStatusCodeEnum, InterfaceAPIResultEnum, \    InterfaceCaseErrorStep, BeforeSqlDBTypeEnumfrom utils import MyLoguru, GenerateTools, RedisClientfrom app.mapper.interface import InterfaceMapper, InterfaceCaseMapperfrom utils.fakerClient import FakerClientfrom utils.transform import Transformfrom .execAssert import ExecAssertsfrom .execExtract import ExecResponseExtractfrom .execScript import ExecScriptForInterfacefrom .execDBScript import ExecDBScriptfrom .sender import HttpSenderfrom .io_sender import APISocketSenderfrom .starter import Starterfrom .writer import InterfaceAPIWriterlog = MyLoguru().get_logger()Interface = TypeVar('Interface', bound=InterfaceModel)InterfaceCase = TypeVar('InterfaceCase', bound=InterFaceCaseModel)Interfaces = List[Interface]async def set_req_url(interface: Interface) -> str:    """    设置请求url    :param interface:    :return:    """    if interface.env_id == -1:        return interface.url    else:        env = await EnvMapper.get_by_id(ident=interface.env_id)        domain = env.host        if env.port:            domain += f":{env.port}"        return domain + interface.urlclass InterFaceRunner:    response: Response | str = None    def __init__(self, starter: Starter, io: APISocketSender | None = None):        self.starter = starter        self.variables = {}        self.io = io        self.sender = HttpSender(self.variables, self.io)    def set_variables(self, data: Dict[str, Any] | List[Dict[str, Any]]) -> Dict[str, Any]:        """        设置变量        :param data:        :return:        """        if isinstance(data, dict):            self.variables.update(**data)        elif isinstance(data, list):            data = GenerateTools.list2dict(data)            self.variables.update(**data)        return data    async def try_interface(self, interface: int) -> Mapping[str, Any]:        """        执行单个接口请求调试        无变量、有前置方法、        需要返回response        """        interface = await InterfaceMapper.get_by_id(ident=interface)        result, _ = await self.__execute_interface(interface)        return result    async def try_group(self, groupId: int):        """        执行接口组        """        interfaces: Interfaces = await InterfaceGroupMapper.query_apis(groupId=groupId)        results = []        for interface in interfaces:            await self.io.send(f"execute  ： {interface}")            result, _ = await self.__execute_interface(interface)            results.append(result)        return results    async def run_interface_by_task(self, interface: Interface, taskResult: InterfaceTaskResultModel) -> bool:        """任务执行api"""        result, _ = await self.__execute_interface(interface=interface, taskResult=taskResult)        await InterfaceAPIWriter.write_interface_result(**result)        return _    async def run_interfaceCase_by_task(self, interfaceCase: InterfaceCase,                                        taskResult: InterfaceTaskResultModel) -> bool:        """任务执行case"""        interfaces: Interfaces = await InterfaceCaseMapper.query_interface_by_caseId(caseId=interfaceCase.id)        await self.io.send(f"用例 {interfaceCase.title} 执行开始。执行人 {self.starter.username}")        await self.io.send(f"查询到关联API x {len(interfaces)} ...")        interfacesNum = len(interfaces)        caseResult = await InterfaceAPIWriter.init_interface_case_result(interfaceCase=interfaceCase,                                                                         taskId=taskResult.id,                                                                         starter=self.starter)        await self.io.send(f"初始化结果模型 。。。 ✅ ID= '{caseResult.uid}'")        _f = True        try:            for index, interface in enumerate(interfaces, start=1):                await self.io.send(f"execute  Step {index} ： {interface}")                if interface.enable == 0:                    await self.io.send(f"execute Step {index} ： 调试禁用 跳过执行")                    continue                result, flag = await self.__execute_interface(interface=interface, caseResult=caseResult)                # 入库                await InterfaceAPIWriter.write_interface_result(**result)                caseResult.progress = round(index / interfacesNum, 1) * 100                if flag:                    caseResult.success_num += 1                else:                    _f = False                    caseResult.result = InterfaceAPIResultEnum.ERROR                    caseResult.fail_num += 1                    if interfaceCase.error_stop == InterfaceCaseErrorStep.STOP:                        caseResult.progress = 100                        break                await InterfaceAPIWriter.write_process(caseResult=caseResult)            caseResult.interfaceLog = "".join(self.io.logs)            await InterfaceAPIWriter.write_interface_case_result(caseResult=caseResult)            return _f        finally:            await self.io.send(f"用例 {interfaceCase.title} 执行结束")            await self.io.send(f"{'====' * 20}")    async def run_interCase(self, interfaceCaseId: int):        """        执行接口用例        """        interfaceCase: InterfaceCase = await InterfaceCaseMapper.get_by_id(ident=interfaceCaseId)        interfaces: Interfaces = await InterfaceCaseMapper.query_interface_by_caseId(caseId=interfaceCaseId)        await self.io.send(f"用例 {interfaceCase.title} 执行开始。执行人 {self.starter.username}")        await self.io.send(f"查询到关联API x {len(interfaces)} ...")        interfacesNum = len(interfaces)        if interfacesNum == 0:            return await self.io.over()        # 加载变量        await self.__init_vars(interfaceCase)        caseResult = await InterfaceAPIWriter.init_interface_case_result(interfaceCase=interfaceCase,                                                                         starter=self.starter)        await self.io.send(f"初始化结果模型 。。。 ✅ ID= '{caseResult.uid}'")        try:            for index, interface in enumerate(interfaces, start=1):                await self.io.send(f"execute  Step {index} ： {interface}")                if interface.enable == 0:                    await self.io.send(f"execute Step {index} ： 调试禁用 跳过执行")                    continue                if interface.is_group:                    group_interfaces: Interfaces = await InterfaceGroupMapper.query_apis(groupId=interface.group_id)                    for _index, _interface in enumerate(group_interfaces, start=1):                        await self.io.send(f"execute Group Step {_index} : {_interface} ")                        result, flag = await self.__execute_interface(interface=_interface, caseResult=caseResult)                        await InterfaceAPIWriter.write_interface_result(**result)                        if not flag:                            caseResult.result = InterfaceAPIResultEnum.ERROR                            break                else:                    result, flag = await self.__execute_interface(interface=interface, caseResult=caseResult)                    # 入库                    await InterfaceAPIWriter.write_interface_result(**result)                    caseResult.progress = round(index / interfacesNum, 1) * 100                    if flag:                        caseResult.success_num += 1                    else:                        caseResult.result = InterfaceAPIResultEnum.ERROR                        caseResult.fail_num += 1                        if interfaceCase.error_stop == InterfaceCaseErrorStep.STOP:                            caseResult.progress = 100                            break                await InterfaceAPIWriter.write_process(caseResult=caseResult)            caseResult.interfaceLog = "".join(self.io.logs)            return await InterfaceAPIWriter.write_interface_case_result(caseResult=caseResult)        finally:            await self.io.send(f"用例 {interfaceCase.title} 执行结束")            await self.io.send(f"{'====' * 20}")            await self.io.over(caseResult.id)    async def __execute_interface(self,                                  interface: InterfaceModel,                                  caseResult: InterfaceCaseResultModel = None,                                  taskResult: InterfaceTaskResultModel = None                                  ) -> Tuple[Mapping[str, Any], bool]:        """        API 执行        返回执行结果，flag        """        # 0、接口处理请求URL        url = await set_req_url(interface)        temp_variables = []        asserts_info = None        try:            # 1、前置变量参数            temp_variables.extend(await self.__exec_before_params(interface.before_params))            # 2、执行前置函数            temp_variables.extend(await self.__exec_before_script(interface.before_script))            # 3.前置sql            temp_variables.extend(await self.__exec_before_sql(interface))            # 4、执行接口请求            self.response = await self.sender(url=url, interface=interface)            # 5、进行断言            asserts_info = await self.__exec_assert(interface)            # 6、出参提取            temp_variables.extend(await self.__exec_extract(interface))            # 7、执行后置函数            temp_variables.extend(await self.__exec_after_script(interface))        except Exception as e:            log.exception(e)            await self.io.send(f"Error occurred: \"{str(e)}\"")            self.response = f"{str(e)} to {url}"        finally:            return await  InterfaceAPIWriter.set_interface_result_info(                starter=self.starter,                interface=interface,                response=self.response,                asserts=asserts_info,                caseResult=caseResult,                taskResult=taskResult,                variables=temp_variables            )    async def __exec_before_script(self, script: str) -> List[Any] | List[Mapping[str, Any]]:        """处理前置脚本"""        if script:            exe = ExecScriptForInterface()            _extracted_vars = self.set_variables(exe.exec_script(script))            await self.io.send(f"前置脚本 = {_extracted_vars}")            _vars = [                {                    InterfaceExtractTargetVariablesEnum.KEY: k,                    InterfaceExtractTargetVariablesEnum.VALUE: v,                    InterfaceExtractTargetVariablesEnum.Target: InterfaceExtractTargetVariablesEnum.BeforeScript                }                for k, v in _extracted_vars.items()            ]            return _vars        return []    async def __exec_before_params(self, before_params: List[Dict[str, Any]] = None):        """处理前置参数"""        if before_params:            _extracted_vars = self.set_variables(before_params)            await self.io.send(f"前置参数 = {_extracted_vars}")            _vars = [                {                    InterfaceExtractTargetVariablesEnum.KEY: k,                    InterfaceExtractTargetVariablesEnum.VALUE: v,                    InterfaceExtractTargetVariablesEnum.Target: InterfaceExtractTargetVariablesEnum.BeforeParams                }                for k, v in _extracted_vars.items()            ]            return _vars        return []    async def __exec_before_sql(self, interface: InterfaceModel):        """        执行前置sql 操作        ## Select            sql:str            - select username from user => [{username:xxx}{username:xxx}][0]            - select username as un  from user => [{un:xxx}{un:xxx}][0]            sql_extracts: [{key:username,jp:$[0].username},{key:username,jp:$[1].username}]            - select username from user => [{username:xxx}{username:xxx}]            ==>  [{username:xx},{username:xx}]        ## Update        """        # 不执行        if not interface.before_sql or not interface.before_db_id:            return []        _db = await DbConfigMapper.get_by_id(interface.before_db_id)        if not _db:            log.warning(f"未找到数据库配置 ID: {interface.before_db_id}")            return []        trans = Transform(self.variables)        script = await trans.transform_target(interface.before_sql.strip())        db_script = ExecDBScript(self.io, script, interface.before_sql_extracts)        match _db.db_type:            case BeforeSqlDBTypeEnum.MYSQL:                res = await db_script.exec_sql(**_db.config)            case BeforeSqlDBTypeEnum.REDIS:                res = await db_script.exec_redis(**_db.config)            case BeforeSqlDBTypeEnum.ORACLE:                res = await db_script.exec_oracle(**_db.config)            case _:                log.warning(f"不支持的数据库类型 {_db.db_type}")                return []        if res:            _vars = [                {                    InterfaceExtractTargetVariablesEnum.KEY: k,                    InterfaceExtractTargetVariablesEnum.VALUE: v,                    InterfaceExtractTargetVariablesEnum.Target: InterfaceExtractTargetVariablesEnum.BeforeSQL                }                for k, v in res.items()            ]            return _vars        return []    async def __exec_assert(self, interface: InterfaceModel):        """        响应断言        前提：        1、有断言        2、有响应        3、响应200        """        if interface.asserts and self.response.status_code == InterfaceResponseStatusCodeEnum.SUCCESS:            _assert = ExecAsserts(self.response)            return await _assert(interface.asserts)    async def __exec_extract(self, interface: InterfaceModel):        """        变量提取        前提：        1、有断言        2、有响应        3、响应200        """        if interface.extracts and self.response.status_code == InterfaceResponseStatusCodeEnum.SUCCESS:            _extract = ExecResponseExtract(response=self.response)            _vars = await _extract(interface.extracts)            await self.io.send(f"响应参数提取 = {_vars}")            self.set_variables(_vars)            return _vars        return []    async def __exec_after_script(self, interface: InterfaceModel):        """        执行后置脚本        """        if interface.after_script and self.response.status_code == InterfaceResponseStatusCodeEnum.SUCCESS:            exe = ExecScriptForInterface(response=self.response)            extracted_vars = self.set_variables(exe.exec_script(interface.after_script))            await self.io.send(f"前置脚本 = {extracted_vars}")            _vars = [                {                    InterfaceExtractTargetVariablesEnum.KEY: k,                    InterfaceExtractTargetVariablesEnum.VALUE: v,                    InterfaceExtractTargetVariablesEnum.Target: InterfaceExtractTargetVariablesEnum.AfterScript                }                for k, v in extracted_vars.items()            ]            return _vars        return []    async def __init_vars(self, interfaceCase: InterfaceCase):        """初始化用例变量"""        try:            interfaceCaseVars: List[InterfaceVariables] = await InterfaceVarsMapper.query_by(case_id=interfaceCase.id)            f = FakerClient()            if interfaceCaseVars:                for var in interfaceCaseVars:                    if var.value.startswith("{{$"):                        _v = var.value[3:-2]                        self.variables[var.key] = f.value(_v)                    else:                        self.variables[var.key] = var.value            if self.variables:                await self.io.send(f"初始化用例变量 = {self.variables}")        except Exception as e:            log.error(e)