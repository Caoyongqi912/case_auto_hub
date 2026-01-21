import json
from json import JSONDecodeError
from typing import List, Mapping, Dict, Any
from mitmproxy import http
from enums import InterfaceRequestTBodyTypeEnum
from utils import log, GenerateTools
from common import rc

Headers = List[Dict[str, Any]] | None
Params = List[Dict[str, Any]] | None
Data = List[Dict[str, Any]] | None
valid_extensions = ("js", "css", "ttf", "jpg", "svg", "gif", "png", 'ts')


class Record:
    """
    开始录制
    redis 存储 record_userId: user record info

    mitmproxy
    """
    prefix = "record_"

    @classmethod
    async def start_record(cls, key_name: str, recordInfo: Dict[str, Any]):
        """
        开始录制
        """
        name = Record.prefix + key_name
        key = await rc.check_key_exist(name)
        if key:
            await rc.remove_key(name)
        log.debug(f"start record {name} {recordInfo}")
        for k, v in recordInfo.items():
            if isinstance(v, list):
                recordInfo[k] = json.dumps(v)
        return await rc.h_set(name=name, value=recordInfo)

    @classmethod
    async def clear_record(cls, ip: str, uid: str):
        """
        停止录制
        """
        IP = cls.prefix + ip
        UID = cls.prefix + uid
        await rc.remove_key(IP)
        await rc.remove_key(UID)
        return

    @classmethod
    async def query_record(cls, name: str):
        """
        查询录制
        """
        name = cls.prefix + name
        data = await rc.l_range(name=name)
        datas = [json.loads(i) for i in data]
        return datas

    @classmethod
    async def deduplication(cls, key_name: str):
        """对url 去重"""
        name = cls.prefix + key_name
        data = await rc.l_range(name=name)
        if not data:
            log.info(f"No data found for key: {name}")
            return
        seen_urls = set()
        unique_data = []
        for item_str in data:
            try:
                item = json.loads(item_str)
                url = item.get('url')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique_data.append(json.dumps(item))
            except json.JSONDecodeError as e:
                log.error(f"Failed to parse JSON: {e}, item: {item_str}")

        log.debug(unique_data)
        await rc.remove_key(name)
        # 使用 pipeline 批量插入数据
        pipeline = rc.r.pipeline()

        for item in unique_data:
            # 将去重后的数据批量推送到 Redis 列表
            pipeline.rpush(name, item)  # 或者 json.dumps(item) 如果是 JSON 格式

        # 执行 pipeline 中的所有命令
        await pipeline.execute()


class InterfaceRecoder:

    async def response(self, flow: http.HTTPFlow) -> None:
        """response 响应回调"""
        if flow.request.method.lower() == "options" or any(ext in flow.request.url for ext in valid_extensions):
            return
        _client = await rc.h_get_all("record_" + flow.client_conn.peername[0])

        methods = json.loads(_client['method'])
        if _client and _client["url"] in flow.request.url \
                and flow.request.method.upper() in methods:
            ir = RecordRequest(flow)
            await rc.l_push("record_" + _client['uid'], ir.map)


class RecordRequest:
    uid: str = None
    url: str | None = None
    method: str | None = None
    headers: Headers = None
    params: Params = None
    body: dict | None = None
    data: Data = None
    body_type: int | None = None
    response: str | None = None

    def __init__(self, flow: http.HTTPFlow) -> None:
        self.flow = flow
        self.url = flow.request.url
        self.method = flow.request.method
        self.set_Headers()
        self.set_Body()
        self.set_response()

    def set_Headers(self):
        if self.flow.request.headers:
            _headers = dict(self.flow.request.headers)
            self.headers = [dict(key=k, value=v, id=GenerateTools.uid()) for k, v in _headers.items()
                            if k not in ["content-length"]]

    def set_Body(self):
        """
        暂支持
        无body
        json body
        data body
        :return:
        """
        requestType = self.flow.request.headers.get("Content-Type")

        if "json" in requestType:
            return self._is_json()
        if "form" in requestType:
            return self._is_data()
        else:
            return self._is_params()

    def set_response(self):
        content_type = self.flow.response.headers.get("Content-Type", "")
        text = self.flow.response.text if self.flow.response.text else ""

        # 获取字符编码
        content_encoding = self.flow.response.headers.get("Content-Encoding", "utf-8")

        try:
            if "json" in content_type.lower():
                self.response = json.dumps(json.loads(text), indent=4, ensure_ascii=False)
            elif "text" in content_type.lower() or "xml" in content_type.lower():
                self.response = text
            else:
                self.response = self.flow.response.data.decode(content_encoding)
        except (JSONDecodeError, UnicodeDecodeError) as e:
            # 记录日志或采取其他措施
            log.error(f"Error processing response: {e}")
            self.response = text

    def _is_json(self):
        try:
            self.body_type = InterfaceRequestTBodyTypeEnum.Json
            self.body = json.loads(self.flow.request.text)
        except json.decoder.JSONDecodeError as e:
            log.error(e)

    def _is_data(self):
        self.body_type = InterfaceRequestTBodyTypeEnum.Data
        self.data = self.__parse_kv_text(self.flow.request.text)

    def _is_params(self):
        self.body_type = InterfaceRequestTBodyTypeEnum.Null
        try:
            query = self.flow.request.query
            self.params = [{"key": k, "value": v} for k, v in dict(query).items()]
        except Exception as e:
            log.error(e)

    @staticmethod
    def __parse_kv_text(text: str):
        """
        将给定的类似 `key=value` 格式用 `&` 连接的文本解析为字典列表，
        每个字典包含 'key' 和 'value' 表示解析后的键值对，并且对键值进行 `unquote` 解引用处理。

        :param text: 待解析的文本，格式如 `key1=value1&key2=value2` 等。
        :return: 解析后的字典列表。
        """
        from urllib.parse import unquote
        pairs = text.split('&')
        result = []
        for pair in pairs:
            key_value = pair.split('=')
            if len(key_value) == 2:
                key = unquote(key_value[0])
                value = unquote(key_value[1])
                result.append({'key': key, 'value': value})
        return result

    @property
    def map(self) -> str:
        m = dict(
            response=self.response,
            create_time=GenerateTools.getTime(1),
            uid=GenerateTools.uid(),
            url=self.url,
            method=self.method,
            headers=self.headers,
            params=self.params,
            data=self.data,
            body=self.body,
            body_type=self.body_type)
        return json.dumps(m, ensure_ascii=False)
