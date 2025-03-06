#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2025/2/14# @Author : cyq# @File : mysqlClient# @Software: PyCharm# @Desc:from typing import Optional, List, Dict, Anyimport aiomysqlfrom app.exception import CommonErrorfrom config import Configfrom utils import MyLogurulog = MyLoguru().get_logger()class MySqlClient:    def __init__(self):        self.pool: aiomysql.Pool | None = None    async def create_pool(self, **kwargs):        """创建 MySQL 连接池"""        self.pool = await aiomysql.create_pool(**kwargs)    @staticmethod    async def connect(db_host,db_port,db_username,db_password,db_database):        try:            await aiomysql.connect(                host=db_host,                port=db_port,                user=db_username,                password=db_password,                db=db_database,            )        except Exception as e:            raise CommonError(str(e))    async def default_pool(self):        data = {            "host": Config.MYSQL_SERVER,            "port": Config.MYSQL_PORT,            "user": "root",            "password": Config.MYSQL_PASSWORD,            "db": Config.MYSQL_DATABASE,            "autocommit": True        }        self.pool = await aiomysql.create_pool(**data)    async def close_pool(self):        """关闭连接池"""        if self.pool:            self.pool.close()            await self.pool.wait_closed()    async def fetch_all(self, query: str) -> List[Dict[str, Any]]:        """查询所有数据"""        async with self.pool.acquire() as conn:            async with conn.cursor(aiomysql.DictCursor) as cur:                await cur.execute(query)                result = await cur.fetchall()                return result    async def fetch_one(self, query: str) -> Optional[Dict[str, Any]]:        """查询单条数据"""        async with self.pool.acquire() as conn:            async with conn.cursor(aiomysql.DictCursor) as cur:                await cur.execute(query)                result = await cur.fetchone()                return result    async def execute(self, query: str):        """执行 SQL 语句（用于 INSERT, UPDATE, DELETE）"""        async with self.pool.acquire() as conn:            async with conn.cursor() as cur:                await cur.execute(query)                await conn.commit()