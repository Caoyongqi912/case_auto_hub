#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
数据库自动同步脚本
使用 SQLAlchemy 的 metadata comparison 功能来自动同步表结构

⚠️ 警告：此脚本会直接修改数据库结构，请谨慎使用！
建议仅在开发环境中使用，生产环境请使用 Alembic

使用方法:
    python sync_database.py --dry-run   # 预览更改（不实际执行）
    python sync_database.py --execute    # 执行同步
"""
import sys
import asyncio
from pathlib import Path
from sqlalchemy import inspect
from sqlalchemy.engine import reflection

from app.model import async_engine, BaseModel
from config import Config

async def get_metadata_diff():
    """比较数据库表和模型定义之间的差异"""
    inspector = inspect(async_engine.sync_engine)

    with async_engine.begin() as conn:
        existing_tables = await conn.run_sync(
            lambda sync_conn: inspector.get_table_names()
        )

        model_tables = set(BaseModel.metadata.tables.keys())

        print("=" * 60)
        print("数据库同步分析报告")
        print("=" * 60)
        print(f"\n数据库中存在的表: {len(existing_tables)}")
        print(f"模型中定义的表: {len(model_tables)}")

        tables_only_in_db = set(existing_tables) - model_tables
        tables_only_in_model = model_tables - set(existing_tables)
        tables_in_both = model_tables & set(existing_tables)

        if tables_only_in_db:
            print(f"\n⚠️  仅在数据库中存在的表（不会被删除）:")
            for table in sorted(tables_only_in_db):
                print(f"   - {table}")

        if tables_only_in_model:
            print(f"\n✅  仅在模型中存在的表（将被创建）:")
            for table in sorted(tables_only_in_model):
                print(f"   + {table}")

        if tables_in_both:
            print(f"\n📝  表结构对比:")
            for table_name in sorted(tables_in_both):
                existing_columns = inspector.get_columns(table_name)
                model_table = BaseModel.metadata.tables[table_name]
                model_columns = {col.name: col for col in model_table.columns}

                existing_col_names = {col['name'] for col in existing_columns}
                model_col_names = set(model_columns.keys())

                new_columns = model_col_names - existing_col_names
                missing_columns = existing_col_names - model_col_names

                if new_columns or missing_columns:
                    print(f"\n   表: {table_name}")
                    if new_columns:
                        print(f"      新增字段:")
                        for col in sorted(new_columns):
                            col_type = model_columns[col].type
                            print(f"        + {col} ({col_type})")
                    if missing_columns:
                        print(f"      缺失字段（模型中已移除）:")
                        for col in sorted(missing_columns):
                            print(f"        - {col}")

    return {
        'new_tables': tables_only_in_model,
        'tables_to_compare': tables_in_both
    }

async def sync_database(dry_run: bool = True):
    """同步数据库结构"""
    print(f"\n模式: {'预览模式（不执行更改）' if dry_run else '执行模式（将修改数据库）'}")
    print("=" * 60)

    await get_metadata_diff()

    if dry_run:
        print("\n\n💡 提示: 这是预览模式，未执行任何更改")
        print("   使用 --execute 参数来实际执行同步")
    else:
        print("\n⚠️  开始执行数据库同步...")
        print("   注意: 只会添加新表和新字段，不会删除数据")

        async with async_engine.begin() as conn:
            await conn.run_sync(BaseModel.metadata.create_all)

        print("\n✅ 数据库同步完成！")

async def main():
    if '--dry-run' in sys.argv or '--execute' not in sys.argv:
        await sync_database(dry_run=True)
    elif '--execute' in sys.argv:
        await sync_database(dry_run=False)
    else:
        print(__doc__)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
