#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/7/23# @Author : cyq# @File : sender# @Software: PyCharm# @Desc:from typing import NoReturn, Union, Mapping, Dictfrom play.exception import APIAssertExceptionfrom play.writer import Writerfrom utils import logfrom utils.io_sender import SocketSenderfrom utils.jsonPathUtil import MyJsonPathfrom app.model.ui import UIStepAPIModel, UIResultModel, UICaseStepsModelfrom play.extract import ExtractManagerfrom play.logWriter import LogWriterfrom utils.httpxClient import HttpxClientfrom utils.assertsUtil import MyAssertsfrom httpx import Response, Requestclass APISender(HttpxClient):    cookie: str = None    response: Response = None    def __init__(self, io: SocketSender, em: ExtractManager):        self.em = em        self.io = io        super().__init__(            hooks={'request': [self.__log_request],                   'response': [self.__log_response]},        )    async def send(self, env: str, stepApi: UIStepAPIModel):        """        :return: response        """        request_info = {}        try:            if stepApi.params:                newParams = await self.__list2Dict(stepApi.params)                request_info['params'] = await self.em.transform_target(newParams)            if stepApi.body_type == 1:                request_info["json"] = await self.em.transform_target(stepApi.body)            await self.io.send(f"🚀 API Hook: request  headers={request_info.get('headers', None)}")            await self.io.send(f"🚀 API Hook: request  params={request_info.get('params', None)}")            await self.io.send(f"🚀 API Hook: request  body={request_info.get('json', None)}")            self.response = await super().__call__(stepApi.method,                                                   env + stepApi.url,                                                   **request_info)            await self.io.send(f"🚀 API Hook: response text={self.response.text}")            return self.response        except Exception as e:            log.exception(repr(e))            raise e    async def setCookie(self, cookie: Dict[str, str]) -> NoReturn:        """        :param cookie:        :return:        """        self.cookie = f"{cookie['name']}={cookie['value']}"    async def add_extracts(self, extracts: list):        """        响应 变量添加        '[{'id': 1723193047893, 'key': 'conId', 'value': '$.data.rows[0].conId', 'target': '1'}]        :param extracts:        :return:        """        for ext in extracts:            jp = MyJsonPath(jsonBody=self.response.json(),                            expr=ext['value'])            newValue = await jp.value()            await self.io.send(f"🚀 API Var: 添加变量 {ext['key']}={newValue}")            await self.em.add_var(key=ext['key'], value=newValue)    async def do_assert(self, stepApi: UIStepAPIModel,                        step: UICaseStepsModel,                        case_result: UIResultModel = None):        """        :param stepApi:        :param step        :param case_result        """        assert_manager = MyAsserts()        assertsInfo = []        for ass in stepApi.asserts:            await self.io.send(f"🚀 API Assert: 开始断言 {ass['desc']}")            jp = MyJsonPath(jsonBody=self.response.json(),                            expr=ass['extraValue'])            actualValue = await jp.value()            if actualValue is None:                await self.io.send(f"🚀 API Assert:{ass['desc']} ⚠️ JsonPath取值为None")            try:                assert_manager.option(assertOpt=ass['assertOpt'],                                      expect=ass["expect"],                                      actual=actualValue,                                      extraValueType=ass['extraValueType'])                await self.io.send(                    f"🚀 API Assert:【{ass['desc']}】 断言成功 ✅ 预期值：{ass['expect']} 实际值：{actualValue}")                # 断言成功 添加结果                assertsInfo.append(                    {**ass,                     "type": "API",                     "stepName": step.name,                     "actual": actualValue,                     "result": True}                )            except AssertionError:                # 断言失败                assertsInfo.append(                    {**ass,                     "type": "API",                     "stepName": step.name,                     "actual": actualValue,                     "result": False}                )                await self.io.send(                    f"🚀 API Assert:【{ass['desc']}】 预期值：{ass['expect']} 实际值：{actualValue}")                if stepApi.go_on == 0:                    await Writer.write_assert_info(case_result, assertsInfo)                    raise APIAssertException(f"【{ass['desc']}】 预期值：{ass['expect']} 实际值：{actualValue}")                else:                    continue        log.debug(assertsInfo)        await Writer.write_assert_info(case_result, assertsInfo)    @staticmethod    async def __list2Dict(params: list) -> dict:        """        :param params:        :return:        """        return {i['key']: i['value'] for i in params}    async def __log_request(self, request: Request) -> None:        await self.io.send(f"🚀 API Hook: request  {request.method.upper()} : {request.url}")    async def __log_response(self, response: Response) -> None:        await self.io.send(f"🚀 API Hook: response status_code >> {response.status_code}")