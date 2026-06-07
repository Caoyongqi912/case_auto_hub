#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
一次性迁移: 给 test_case_mind 增加 plan_id 字段

项目未上线时,直接 DROP 旧表是最快的路径;
若已有数据,执行幂等 ALTER TABLE。

使用: python script/migrate_mind_case_plan_id.py [--drop]
"""
import asyncio
import sys
from pathlib import Path

# 允许以绝对路径直接执行本脚本（无需先 cd 到项目根）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import text

from app.model import async_engine


DROP_SQL = "DROP TABLE IF EXISTS test_case_mind"
ADD_COLUMN_SQL_TEMPLATE = """
ALTER TABLE test_case_mind
  ADD COLUMN plan_id INT NULL COMMENT '所属计划（脑图按计划维度时填写）',
  ADD INDEX idx_plan_id (plan_id)
"""
ADD_FK_SQL_TEMPLATE = """
ALTER TABLE test_case_mind
  ADD CONSTRAINT fk_test_case_mind_plan_id
  FOREIGN KEY (plan_id) REFERENCES case_plan(id) ON DELETE CASCADE
"""


async def drop_table() -> None:
    async with async_engine.begin() as conn:
        await conn.execute(text(DROP_SQL))
    print("[migrate] DROP test_case_mind OK")


async def add_columns() -> None:
    async with async_engine.begin() as conn:
        await conn.execute(text(ADD_COLUMN_SQL_TEMPLATE))
        try:
            await conn.execute(text(ADD_FK_SQL_TEMPLATE))
        except Exception as e:
            # 已有同名 FK 时忽略
            print(f"[migrate] add FK skipped: {e}")
    print("[migrate] ADD plan_id OK")


async def main() -> None:
    if "--drop" in sys.argv:
        await drop_table()
    await add_columns()


if __name__ == "__main__":
    asyncio.run(main())
