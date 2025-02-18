#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2025/2/18# @Author : cyq# @File : oracleClient# @Software: PyCharm# @Desc:import asyncioimport cx_Oraclefrom cx_Oracle import Connectionclass OracleClient:    connection: Connection = None    cursor = None    async def connect(self, host: str, port: str | int, service_name: str, username: str, password: str):        loop = asyncio.get_event_loop()        self.connection = await loop.run_in_executor(None, self._connect_sync, host, port, service_name, username,                                                     password)        self.cursor = self.connection.cursor()    @staticmethod    def _connect_sync(host: str, port: str, service_name: str, username: str, password: str):        """同步连接数据库"""        dsn = cx_Oracle.makedsn(host, port, service_name=service_name)        # cx_Oracle.init_oracle_client(lib_dir="/Users/cyq/Downloads/instantclient_19_16")        return cx_Oracle.connect(user=username, password=password, dsn=dsn)    async def fetch_all(self, query, params=None):        """异步查询数据库"""        loop = asyncio.get_event_loop()        return await loop.run_in_executor(None, self._fetch_all_sync, query, params)    def _fetch_all_sync(self, query, params):        """同步执行查询"""        self.cursor.execute(query, params or [])        return self.cursor.fetchall()    async def execute(self, query, params=None):        """异步执行插入/更新/删除操作"""        loop = asyncio.get_event_loop()        await loop.run_in_executor(None, self._execute_sync, query, params)    def _execute_sync(self, query, params):        """同步执行非查询操作"""        self.cursor.execute(query, params or [])        self.connection.commit()    async def close(self):        """关闭连接"""        loop = asyncio.get_event_loop()        await loop.run_in_executor(None, self._close_sync)    def _close_sync(self):        """同步关闭连接"""        if self.cursor:            self.cursor.close()        if self.connection:            self.connection.close()# 使用示例async def main():    dsn = "your_dsn_here"  # 替换为实际的 DSN    user = "your_username"  # 替换为用户名    password = "your_password"  # 替换为密码    db = OracleClient()    await db.connect(host="oracle.cbs-beijing.sit1.private",                     port="1521",                     service_name="cbssit",                     username="SCM", password="OdyI28suOjTcgld")    # 查询示例    sql = """       select S.CON_ID    from SCM_SIGN_CONTRACT S             left join perf_prorate_detail P on S.CON_ID = P.CONTRACT_ID    where S.CONTRACT_STATUS = 2      and S.AUDIT_STATUS = 10      and S.COMMISSION_COLLECTED = 1    --   and S.FIRST_SIGN_DATE > to_date('{{first_month}}', 'yyyy-mm-dd')      and S.CONTRACT_TYPE = 2      and P.BELONGER_VERSIONID = 62800    order by S.CON_ID desc     """    # 执行插入/更新/删除示例    await db.execute(sql )    await db.close()# 运行示例if __name__ == "__main__":    asyncio.run(main())