#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2025/2/17# @Author : cyq# @File : execSql# @Software: PyCharm# @Desc:from typing import List, Dictfrom common import RedisClientfrom interface.io_sender import APISocketSenderfrom common.mysqlClient import MySqlClientfrom utils import log, MyJsonPathimport refrom common.oracleClient import OracleClientSELECT_KEYWORDS = ("select", "SELECT")class ExecDBScript:    def __init__(self, io: APISocketSender, script_str: str,                 extracts: List[Dict[str, str]] = None,                 onlySearch: bool = False):        self._io = io        self._script = re.sub(r'\s+', ' ', script_str).strip(";")        self._extract = extracts        self._onlySearch = onlySearch        self.mysql_client = MySqlClient()        self.redis_client = RedisClient()        self.oracle_client = OracleClient()    async def exec_sql(self, **kwargs):        """执行sql"""        result = {}        try:            await self.mysql_client.create_pool(**kwargs)            if self._script.startswith(SELECT_KEYWORDS):                keys = await self.__get_keys()                try:                    search_data = await self.mysql_client.fetch_all(self._script)                    await self._io.send(f"Get Search Data {search_data}")                    if self._onlySearch:                        return search_data                    if not search_data:                        return result                except Exception as e:                    await self._io.send(f"Fetch Sql Error: {e}")                    return None                # 如果没有将keys 赋值查到的第一个数据返回                first_data = search_data[0]                for key in keys:                    if first_data.get(key):                        result[key] = first_data.get(key)                # 如果有获取预期                if self._extract:                    for item in self._extract:                        j = MyJsonPath(search_data, item.get('jp'))                        value = await j.value()                        if value:                            result[item["key"]] = value                return result            else:                await self.mysql_client.execute(self._script)                return None        except Exception as e:            log.error(e)            await self._io.send(f"Exec Sql Error: {e}")            return result        finally:            await self.mysql_client.close_pool()    async def exec_redis(self, **kwargs):        result = {}        try:            await self.redis_client.set_pool(**kwargs)            value = await self.redis_client.execute_script(self._script)            await self._io.send(f"Exec Redis values: {value}")            if self._onlySearch:                return value            if self._extract:                for item in self._extract:                    j = MyJsonPath(value, item.get('jp'))                    value = await j.value()                    if value:                        result[item["key"]] = value            return result        except Exception as e:            log.error(e)            await self._io.send(f"Exec Redis Error: {e}")            return result        finally:            await self.redis_client.close_pool()    async def exec_oracle(self, **kwargs):        """执行 oracle sql"""        result = {}        try:            await self.oracle_client.connect(**kwargs)            if self._script.startswith(SELECT_KEYWORDS):                keys = await self.__get_keys()                log.debug(f"Oracle Get Keys {keys}")                try:                    log.debug(f"script {self._script}")                    search_data = await self.oracle_client.fetch_all(self._script)                    await self._io.send(f"Oracle Get Search Data {search_data}")                    if self._onlySearch:                        return search_data                    if not search_data:                        return result                except Exception as e:                    await self._io.send(f"Fetch Sql Error: {e}")                    return None                # 如果没有将keys 赋值查到的第一个数据返回                first_data = search_data[0]                log.debug(f"Oracle Get First Data {first_data}")                for key in keys:                    _key = key.upper()                    if first_data.get(_key):                        result[_key] = first_data.get(_key)                # 如果有获取预期                if self._extract:                    for item in self._extract:                        j = MyJsonPath(search_data, item.get('jp'))                        value = await j.value()                        if value:                            result[item["key"]] = value                return result            else:                await self.oracle_client.execute(self._script)                return None        except Exception as e:            log.error(e)            await self._io.send(f"Exec Oracle Error: {e}")            return result        finally:            await self.oracle_client.close()    async def __get_keys(self):        params = re.findall(r'select(.*?)from', self._script, re.IGNORECASE)[0].strip().split(",")        keys = []        for i in params:            if " as " in i:                _ = i.split(" as ")[1]                keys.append(_.strip())            else:                keys.append(i.strip())        return keys    async def verify_str(self, key: str):        """判断自大小写"""