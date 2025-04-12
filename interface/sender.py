#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/22# @Author : cyq# @File : sender# @Software: PyCharm# @Desc:import asyncioimport jsonfrom typing import Any, Dict, List, TypeVar, Tuplefrom httpx import Responsefrom app.mapper.interface import InterfaceGlobalHeaderMapperfrom app.model.interface import InterfaceModelfrom enums import InterfaceRequestTBodyTypeEnum, InterfaceRequestMethodEnumfrom utils import GenerateTools, MyLoguru, logfrom common.fakerClient import FakerClientfrom common.httpxClient import HttpxClientfrom .starter import APIStarterimport reLOG = MyLoguru().get_logger()Interface = TypeVar('Interface', bound=InterfaceModel)class HttpSender(HttpxClient):    def __init__(self, variables: Dict[str, Any], starter: APIStarter):        self.variables = variables        self.starter = starter        super().__init__(log=self.starter.send)    async def __call__(self, url: str, interface: Interface, **kwargs) -> Response:        """        :param interface        :return:        """        _request_data = await self.set_req_info(interface)        url = await self.transform_target(target=url)        await self.starter.send(f"Request INFO : {json.dumps(_request_data, ensure_ascii=False)}")        return await super().__call__(method=interface.method.lower(),                                      url=url,                                      **_request_data)    async def transform_target(self, target: Any):        """        参数转换        数据转换        """        # 如果单纯字符串        if isinstance(target, str):            return await self._transformStr(target)        # 如果是字典        if isinstance(target, dict):            return await self._transFormObj(target)        # 如果是列表        if isinstance(target, list):            return await self._transFormList(target)        if isinstance(target, tuple):            return await self._transFormTuple(target)    async def _transformStr(self, target: str) -> str:        """        字符串替换        """        if target.startswith("{{") and target.endswith("}}"):            # 处理 {{$xx}} 格式变量            extractKey = target[2:-2]            if extractKey.startswith("$"):                extractKey = extractKey[1:]                f = FakerClient()                return f.value(extractKey)            return self.variables.get(extractKey, target)        else:            pattern = r"{{(.*?)}}"            return re.sub(pattern, lambda match: str(self.variables.get(match.group(1), match.group(0))), target)    async def _transFormObj(self, target: Dict[str, Any]) -> Dict[str, Any]:        """        字典替换        :param target        """        return {key: await self.transform_target(value) for key, value in target.items()}    async def _transFormList(self, target: List[Any]) -> List[Any]:        """        列表替换        """        return [await self.transform_target(item) for item in target]    async def _transFormTuple(self, target: Tuple[Any, ...]) -> Tuple[Any, ...]:        """        元组替换        """        transformed_items = []        for item in target:            transformed = await self.transform_target(item)            transformed_items.append(transformed)        return tuple(transformed_items)    async def set_req_info(self, interface: Interface):        """        处理并构建HTTP请求信息        Args:            interface: 接口对象，包含请求方法、头信息、参数等        Returns:            包含完整请求信息的字典，可用于httpx等HTTP客户端        """        # 初始化请求数据字典        _request_data = {            InterfaceRequestTBodyTypeEnum.HEADERS: {},            'follow_redirects': bool(interface.follow_redirects),            'read': interface.response_timeout,            'connect': interface.connect_timeout        }        # 处理headers - 全局headers和自定义headers合并        await self._process_headers(_request_data, interface)        # 根据请求方法处理参数或请求体        if interface.method == InterfaceRequestMethodEnum.GET:            await self._process_get_params(_request_data, interface)        else:            await self._process_request_body(_request_data, interface)        # 并行转换请求数据中的变量        await self._transform_request_data(_request_data)        log.debug(f"Final request data: {_request_data}")        return _request_data    @staticmethod    async def _process_headers(request_data: Dict[str, Any], interface: Interface) -> None:        """处理请求头信息"""        # 获取全局headers        global_headers = await InterfaceGlobalHeaderMapper.query_all()        if global_headers:            for header in global_headers:                request_data[InterfaceRequestTBodyTypeEnum.HEADERS].update(header.map)        # 添加自定义headers        if interface.headers:            request_data[InterfaceRequestTBodyTypeEnum.HEADERS].update(                GenerateTools.list2dict(interface.headers)            )    @staticmethod    async def _process_get_params(request_data: Dict[str, Any], interface: Interface) -> None:        """处理GET请求参数"""        if interface.params:            request_data[InterfaceRequestTBodyTypeEnum.PARAMS] = GenerateTools.list2dict(                interface.params            )    async def _process_request_body(self, request_data: Dict[str, Any], interface: Interface) -> None:        """处理非GET请求的请求体"""        body_data, content_type = await self._filter_request_body(interface)        if content_type:            request_data[InterfaceRequestTBodyTypeEnum.HEADERS]["Content-Type"] = content_type        if body_data:            request_data.update(**body_data)    @staticmethod    async def _filter_request_body(interface: Interface) -> Tuple[Dict[str, Any] | None, str | None]:        """根据接口请求体类型处理请求体数据        Args:            interface: 接口对象，包含请求体相关数据        Returns:            Tuple[处理后的请求体字典, Content-Type字符串]            如果不需要请求体则返回 (None, None)        """        log.info(f"request body = {interface.body}")        log.info(f"request body_type = {interface.body_type}")        if not interface.body_type or interface.body_type == InterfaceRequestTBodyTypeEnum.Null:            return None, None        match interface.body_type:            case InterfaceRequestTBodyTypeEnum.Json:                if interface.body:                    return (                        {InterfaceRequestTBodyTypeEnum.JSON: interface.body},                        "application/json"                    )            case InterfaceRequestTBodyTypeEnum.UrlEncoded:                if interface.data:                    return (                        {InterfaceRequestTBodyTypeEnum.FORM_DATA: GenerateTools.list2dict(interface.data)},                        "application/x-www-form-urlencoded"                    )            case InterfaceRequestTBodyTypeEnum.Data:                if interface.data:                    data = GenerateTools.list2dict(interface.data)                    fields = {k: (None, str(v)) for k, v in data.items()}                    return (                        {InterfaceRequestTBodyTypeEnum.FORM_FILES: fields},                        None  # Content-Type将由httpx自动设置                    )            case _:                log.warning(f"Unsupported body type: {interface.body_type}")                return None, None    async def _transform_request_data(self, request_data: Dict[str, Any]) -> None:        """并行转换请求数据中的变量"""        transform_tasks = [            self.transform_target(value)            for value in request_data.values()            if value is not None        ]        transformed_values = await asyncio.gather(*transform_tasks)        for key, value in zip(request_data.keys(), transformed_values):            if value is not None:                request_data[key] = value