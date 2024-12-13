#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/26# @Author : cyq# @File : writer# @Software: PyCharm# @Desc:from typing import Mapping, AnyStr, Any, Listfrom httpx import Responsefrom app.mapper.interface import InterfaceMapper, InterfaceResultMapperfrom app.mapper.interface.interfaceResultMapper import InterfaceCaseResultMapperfrom app.model.base import Userfrom app.model.interface import InterfaceModel, InterFaceCaseModel, InterfaceCaseResultModelfrom enums import InterfaceAPIResultEnum, InterfaceAPIStatusEnumfrom utils import MyLogurufrom datetime import datetimelog = MyLoguru().get_logger()def calculate_time_difference(a: str):    # 将字符串格式的时间转换为 datetime 对象    time_a = datetime.strptime(a, '%Y-%m-%d %H:%M:%S')    # 获取当前时间    time_b = datetime.now()    # 计算时间差    time_diff = time_b - time_a    # 获取小时、分钟、秒和微秒    seconds = time_diff.total_seconds()    hours = int(seconds // 3600)    minutes = int((seconds % 3600) // 60)    seconds = seconds % 60    # 格式化秒数到小数点后 2 位    formatted_time = f"{hours:02}:{minutes:02}:{seconds:05.2f}"    return formatted_timeclass InterfaceAPIWriter:    @staticmethod    async def init_interface_case_result(starter: User,                                         interfaceCase: InterFaceCaseModel) -> InterfaceCaseResultModel:        """        初始化        :param starter:        :param interfaceCase:        :return:        """        init_info = dict(            interfaceCaseID=interfaceCase.id,            interfaceCaseName=interfaceCase.title,            interfaceCaseUid=interfaceCase.uid,            interfaceCaseDesc=interfaceCase.desc,            interfaceCaseProjectId=interfaceCase.project_id,            interfaceCasePartId=interfaceCase.part_id,            total_num=interfaceCase.apiNum,            starterId=starter.id,            starterName=starter.username,            status=InterfaceAPIStatusEnum.RUNNING        )        return await InterfaceCaseResultMapper.init(**init_info)    @staticmethod    async def write_process(caseResult: InterfaceCaseResultModel):        """写进度"""        return await InterfaceCaseResultMapper.set_result_field(caseResult)    @staticmethod    async def finally_interface_case_result(caseResult: InterfaceCaseResultModel):        """写结果"""        if caseResult.fail_num > 1:            caseResult.result = InterfaceAPIResultEnum.ERROR        else:            caseResult.result = InterfaceAPIResultEnum.SUCCESS        caseResult.useTime = calculate_time_difference(caseResult.map['startTime'])        caseResult.status = InterfaceAPIStatusEnum.OVER        return await InterfaceCaseResultMapper.set_result_field(caseResult)    @staticmethod    async def writer_interface_result(            starter: User,            interface: InterfaceModel,            response: Response | str = None,            no_db: bool = True,            asserts: List[Mapping[str, Any]] = None,            caseResult: InterfaceCaseResultModel = None,            variables: List[Mapping[str, Any]] = None) -> Mapping[str, Any] | None:        """        写结果        :param no_db: 是否写入DB        :param starter： 执行人        :param interface: 接口实体        :param response: 响应结果对象        :param variables: 变量        :param asserts:断言信息        :param caseResult        """        _interfaceBaseInfo = dict(            interfaceID=interface.id,            interfaceName=interface.name,            interfaceUid=interface.uid,            interfaceDesc=interface.desc,            starterId=starter.id,            starterName=starter.username,            interfaceProjectId=interface.project_id,            interfacePartId=interface.part_id,            interfaceEnvId=interface.env_id        )        _response = dict()        _response['extracts'] = variables        _response['asserts'] = asserts        _response['result'] = InterfaceAPIResultEnum.SUCCESS        if asserts:            for i in asserts:                if i['result'] is False:                    _response['result'] = InterfaceAPIResultEnum.ERROR                    break        if isinstance(response, str):            _response['response_status'] = 500            _response['response_txt'] = response            _response['result'] = InterfaceAPIResultEnum.ERROR        elif isinstance(response, Response):            _response[                'result'] = InterfaceAPIResultEnum.SUCCESS if response.status_code == 200 else InterfaceAPIResultEnum.ERROR            _response['response_status'] = response.status_code            _response['response_txt'] = response.text            _response['response_head'] = dict(response.headers)            _response['request_head'] = dict(response.request.headers)            _response['request_method'] = response.request.method.upper()            _response['useTime'] = response.elapsed.total_seconds()        if caseResult:            _interfaceBaseInfo['interface_case_result_Id'] = caseResult.id        if no_db is False:            await InterfaceResultMapper.set_result(**_interfaceBaseInfo,                                                   **_response)        log.debug(f"{_interfaceBaseInfo}")        log.debug(f"{_response}")        return {**_interfaceBaseInfo, **_response}