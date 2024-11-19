#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/7/3# @Author : cyq# @File : httpxClient# @Software: PyCharm# @Desc:import httpxfrom httpx import Responsefrom utils import logclass HttpxClient:    def __init__(self, hooks: dict = None, **kwargs):        default_event_hooks = {'request': [self.log_request],                               'response': [self.log_response]}        self.client = httpx.AsyncClient(            timeout=30,            **kwargs,        )        self.client.event_hooks = hooks or default_event_hooks    async def __call__(self,                       method: str,                       url: str,                       **kwargs):        """        :param method:        :param url:        :param kwargs:        :return:        """        return await self.invoke(method=method.lower(),                                 url=url,                                 **kwargs)    async def invoke(self, method, url, **kwargs) -> Response:        response = await getattr(self.client, method)(            url,            **kwargs        )        return response    @staticmethod    async def log_request(request) -> None:        log.info(f"Hook: request  {request.method.upper()} : {request.url}")    @staticmethod    async def log_response(response) -> None:        log.info(f"Hook: request status_code >> {response.status_code}")