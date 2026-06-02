#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/6/1
# @Author : cyq
# @File : admin_db_mcp_server
# @Software: PyCharm
# @Desc: caseHub MySQL MCP Server
#       Connects to a local MySQL instance as user `root` (override via env),
#       exposes CRUD/schema tools over the stdio MCP transport.
#       Config (env):
#         MYSQL_HOST      (default 127.0.0.1)
#         MYSQL_PORT      (default 3306)
#         MYSQL_USER      (default root)
#         MYSQL_PASSWORD  (default sdkjfhsdkjhfsdkhfksd)
#         MYSQL_DB        (default caseHub)
#         MYSQL_QUERY_LIMIT (default 1000)  -- safety cap for SELECT row count
#         MYSQL_ALLOW_WRITE (default 0)     -- set 1 to allow DML/DDL tools

import asyncio
import datetime
import decimal
import os
import re
from contextlib import asynccontextmanager
from typing import Any

import aiomysql
from mcp.server.fastmcp import FastMCP


# ---------- config (env-driven, defaults match the user-provided creds) ----------

HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
PORT = int(os.getenv("MYSQL_PORT", "3306"))
USER = os.getenv("MYSQL_USER", "root")
PASSWORD = os.getenv("MYSQL_PASSWORD", "sdkjfhsdkjhfsdkhfksd")
DATABASE = os.getenv("MYSQL_DB", "caseHub")
QUERY_LIMIT = int(os.getenv("MYSQL_QUERY_LIMIT", "1000"))
ALLOW_WRITE = os.getenv("MYSQL_ALLOW_WRITE", "0") == "1"


# ---------- connection pool ----------

class MySQLClient:
    def __init__(self) -> None:
        self._pool: aiomysql.Pool | None = None
        self._lock = asyncio.Lock()

    async def _ensure_pool(self) -> aiomysql.Pool:
        if self._pool is not None:
            return self._pool
        async with self._lock:
            if self._pool is None:
                self._pool = await aiomysql.create_pool(
                    host=HOST,
                    port=PORT,
                    user=USER,
                    password=PASSWORD,
                    db=DATABASE,
                    autocommit=True,
                    charset="utf8mb4",
                    minsize=1,
                    maxsize=5,
                    connect_timeout=10,
                )
        return self._pool

    @asynccontextmanager
    async def cursor(self, dict_cursor: bool = True):
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            cur_cls = aiomysql.DictCursor if dict_cursor else aiomysql.Cursor
            async with conn.cursor(cur_cls) as cur:
                yield cur

    async def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None


client = MySQLClient()


# ---------- helpers ----------

def _to_jsonable(value: Any) -> Any:
    if isinstance(value, decimal.Decimal):
        return float(value) if value == value.to_integral_value() and value.as_tuple().exponent >= 0 else str(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, datetime.timedelta):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    return value


def _serialize_rows(rows: list[dict]) -> list[dict]:
    return [{k: _to_jsonable(v) for k, v in row.items()} for row in rows]


def _is_select_only(sql: str) -> bool:
    stripped = re.sub(r"--.*?$|/\*.*?\*/", "", sql, flags=re.DOTALL | re.MULTILINE).strip()
    if not stripped:
        return False
    head = stripped.split(";", 1)[0].lstrip().lower()
    if not (head.startswith("select") or head.startswith("with") or head.startswith("show")
            or head.startswith("describe") or head.startswith("explain") or head.startswith("desc")):
        return False
    forbidden = ("insert ", "update ", "delete ", "replace ", "drop ", "truncate ",
                 "alter ", "create ", "grant ", "revoke ", "rename ")
    lowered = " " + head + " "
    return not any(token in lowered for token in forbidden)


def _ensure_write_allowed() -> None:
    if not ALLOW_WRITE:
        raise PermissionError(
            "write operations are disabled. set MYSQL_ALLOW_WRITE=1 to enable DML/DDL tools."
        )


# ---------- MCP server ----------

mcp = FastMCP(
    name="casehub-mysql",
    instructions=(
        "MySQL MCP server for the `caseHub` database. Read-only by default. "
        "Use `list_databases` to discover, `list_tables` / `describe_table` to inspect schema, "
        "`execute_query` for safe SELECTs, and `execute_sql` for writes (requires MYSQL_ALLOW_WRITE=1)."
    ),
)


@mcp.tool()
async def ping() -> dict:
    """Health check: returns the server-side version, current database and user."""
    async with client.cursor() as cur:
        await cur.execute("SELECT VERSION() AS version, DATABASE() AS db, CURRENT_USER() AS user")
        row = await cur.fetchone()
    return _serialize_rows([row])[0]


@mcp.tool()
async def list_databases() -> list[str]:
    """List all databases visible to the current user (SHOW DATABASES)."""
    async with client.cursor(dict_cursor=False) as cur:
        await cur.execute("SHOW DATABASES")
        rows = await cur.fetchall()
    return [r[0] for r in rows]


@mcp.tool()
async def list_tables(schema: str | None = None, like: str | None = None) -> list[dict]:
    """List tables (and views) in a schema.

    Args:
        schema: target schema name. defaults to the connected database.
        like: optional LIKE pattern (e.g. "ui_%") to filter table names.
    """
    target = schema or DATABASE
    sql = "SHOW FULL TABLES FROM `" + target + "`"
    params: tuple = ()
    if like:
        sql += " LIKE %s"
        params = (like,)
    async with client.cursor(dict_cursor=False) as cur:
        await cur.execute(sql, params)
        rows = await cur.fetchall()
    return [{"name": r[0], "type": r[1]} for r in rows]


@mcp.tool()
async def describe_table(table_name: str) -> list[dict]:
    """Return column definitions for a table (DESCRIBE).

    Args:
        table_name: table name (without backticks).
    """
    if not table_name or not re.fullmatch(r"[A-Za-z0-9_$.]+", table_name):
        raise ValueError("invalid table_name")
    async with client.cursor() as cur:
        await cur.execute("DESCRIBE `" + table_name + "`")
        rows = await cur.fetchall()
    return _serialize_rows(rows)


@mcp.tool()
async def get_table_indexes(table_name: str) -> list[dict]:
    """Return index information for a table (SHOW INDEX).

    Args:
        table_name: table name.
    """
    if not table_name or not re.fullmatch(r"[A-Za-z0-9_$.]+", table_name):
        raise ValueError("invalid table_name")
    async with client.cursor() as cur:
        await cur.execute("SHOW INDEX FROM `" + table_name + "`")
        rows = await cur.fetchall()
    return _serialize_rows(rows)


@mcp.tool()
async def get_table_ddl(table_name: str) -> str:
    """Return the CREATE TABLE statement (uses SHOW CREATE TABLE).

    Args:
        table_name: table name.
    """
    if not table_name or not re.fullmatch(r"[A-Za-z0-9_$.]+", table_name):
        raise ValueError("invalid table_name")
    async with client.cursor(dict_cursor=False) as cur:
        await cur.execute("SHOW CREATE TABLE `" + table_name + "`")
        row = await cur.fetchone()
    if not row:
        return ""
    return row[1] if len(row) > 1 else ""


@mcp.tool()
async def execute_query(sql: str, params: list | None = None, limit: int | None = None) -> dict:
    """Run a read-only query (SELECT / WITH / SHOW / DESCRIBE / EXPLAIN) and return rows.

    Args:
        sql: SQL statement. Must be a read-only statement; writes are rejected.
        params: optional positional parameter list for `%s` placeholders.
        limit: max rows to return. defaults to MYSQL_QUERY_LIMIT (capped at 1000).
    """
    if not _is_select_only(sql):
        raise ValueError("execute_query only accepts read-only statements")
    eff_limit = max(1, min(limit or QUERY_LIMIT, 1000))
    args = tuple(params) if params else ()

    async with client.cursor() as cur:
        await cur.execute(sql, args)
        rows = await cur.fetchmany(eff_limit)
        truncated = len(rows) == eff_limit and (await cur.fetchone() is not None)

    return {
        "rows": _serialize_rows(list(rows)),
        "row_count": len(rows),
        "limit": eff_limit,
        "truncated": truncated,
    }


@mcp.tool()
async def execute_sql(sql: str, params: list | None = None) -> dict:
    """Run a write statement (INSERT / UPDATE / DELETE / DDL). Requires MYSQL_ALLOW_WRITE=1.

    Args:
        sql: SQL statement to execute.
        params: optional positional parameter list for `%s` placeholders.
    """
    _ensure_write_allowed()
    if _is_select_only(sql):
        raise ValueError("use execute_query for read-only statements")
    args = tuple(params) if params else ()

    async with client.cursor(dict_cursor=False) as cur:
        await cur.execute(sql, args)
        affected = cur.rowcount
        last_id = cur.lastrowid

    return {"affected_rows": int(affected or 0), "last_insert_id": int(last_id or 0)}


@mcp.tool()
async def server_info() -> dict:
    """Return non-sensitive connection settings and feature flags."""
    return {
        "host": HOST,
        "port": PORT,
        "user": USER,
        "database": DATABASE,
        "query_limit": QUERY_LIMIT,
        "allow_write": ALLOW_WRITE,
    }


if __name__ == "__main__":
    try:
        mcp.run(transport="stdio")
    finally:
        asyncio.run(client.close())
