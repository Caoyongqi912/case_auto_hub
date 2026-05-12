#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/5/7
# @Author : cyq
# @File : mysql_mcp_server
# @Software: PyCharm
# @Desc: MySQL MCP Server - 使用 stdio 协议与 AI 助手通信

import asyncio
import json
import sys
from typing import Any

import aiomysql

from config import LocalConfig


class MySQLMCPServer:
    def __init__(self):
        self.pool: aiomysql.Pool | None = None

    async def initialize(self):
        await self.create_pool()

    async def create_pool(self):
        data = {
            "host": LocalConfig.MYSQL_SERVER,
            "port": LocalConfig.MYSQL_PORT,
            "user": "root",
            "password": LocalConfig.MYSQL_PASSWORD,
            "db": LocalConfig.MYSQL_DATABASE,
            "autocommit": True,
            "charset": "utf8mb4"
        }
        self.pool = await aiomysql.create_pool(**data)

    async def close_pool(self):
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()

    async def list_tables(self) -> list[str]:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SHOW TABLES")
                result = await cur.fetchall()
                return [row[0] for row in result]

    async def get_table_info(self, table_name: str) -> list[dict]:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(f"DESCRIBE `{table_name}`")
                result = await cur.fetchall()
                return [dict(row) for row in result]

    async def execute_query(self, sql: str) -> list[dict]:
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT"):
            raise ValueError("只支持 SELECT 查询")

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql)
                result = await cur.fetchall()
                return [dict(row) for row in result]

    async def execute_sql(self, sql: str) -> dict:
        sql_upper = sql.strip().upper()
        if sql_upper.startswith("SELECT"):
            raise ValueError("SELECT 查询请使用 execute_query")

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                await conn.commit()
                return {
                    "affected_rows": cur.rowcount,
                    "last_insert_id": cur.lastrowid if cur.lastrowid else 0
                }

    async def get_databases(self) -> list[str]:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SHOW DATABASES")
                result = await cur.fetchall()
                return [row[0] for row in result]


server = MySQLMCPServer()


async def handle_request(request: dict) -> dict:
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "initialize":
        await server.initialize()
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mysql-mcp-server", "version": "1.0.0"}
            }
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "tools": [
                    {
                        "name": "list_tables",
                        "description": "获取当前数据库的所有表名",
                        "inputSchema": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    },
                    {
                        "name": "get_table_info",
                        "description": "获取指定表的结构信息（字段名、类型、是否可空等）",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "table_name": {
                                    "type": "string",
                                    "description": "表名（大写）"
                                }
                            },
                            "required": ["table_name"]
                        }
                    },
                    {
                        "name": "execute_query",
                        "description": "执行 SELECT 查询语句（仅支持 SELECT）",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "sql": {
                                    "type": "string",
                                    "description": "SQL 查询语句"
                                }
                            },
                            "required": ["sql"]
                        }
                    },
                    {
                        "name": "execute_sql",
                        "description": "执行 INSERT/UPDATE/DELETE 等 SQL 语句",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "sql": {
                                    "type": "string",
                                    "description": "SQL 语句"
                                }
                            },
                            "required": ["sql"]
                        }
                    }
                ]
            }
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        try:
            if tool_name == "list_tables":
                result = await server.list_tables()
                content = [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]

            elif tool_name == "get_table_info":
                table_name = arguments.get("table_name", "")
                result = await server.get_table_info(table_name)
                content = [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]

            elif tool_name == "execute_query":
                sql = arguments.get("sql", "")
                result = await server.execute_query(sql)
                content = [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]

            elif tool_name == "execute_sql":
                sql = arguments.get("sql", "")
                result = await server.execute_sql(sql)
                content = [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]

            else:
                raise ValueError(f"Unknown tool: {tool_name}")

            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "content": content
                }
            }

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }

    return {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "error": {
            "code": -32601,
            "message": f"Unknown method: {method}"
        }
    }


async def main():
    await server.initialize()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
            response = await handle_request(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError as e:
            error_response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {e}"
                }
            }
            print(json.dumps(error_response), flush=True)

    await server.close_pool()


if __name__ == "__main__":
    asyncio.run(main())