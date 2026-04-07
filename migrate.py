#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
数据库迁移管理脚本
使用方法:
    python migrate.py init          - 初始化数据库（首次使用）
    python migrate.py migrate      - 生成迁移脚本
    python migrate.py upgrade      - 执行迁移
    python migrate.py downgrade    - 回滚迁移
    python migrate.py show         - 查看当前版本
"""
import sys
import asyncio
import subprocess
from pathlib import Path

def run_command(cmd: list[str]) -> None:
    """执行命令"""
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    sys.exit(result.returncode)

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "init":
        print("初始化数据库表...")
        asyncio.run(init_database())
    elif command == "migrate":
        print("生成迁移脚本...")
        run_command(["alembic", "revision", "--autogenerate", "-m", "auto_migration"])
    elif command == "upgrade":
        print("执行迁移...")
        run_command(["alembic", "upgrade", "head"])
    elif command == "downgrade":
        revision = sys.argv[2] if len(sys.argv) > 2 else "-1"
        print(f"回滚到版本: {revision}")
        run_command(["alembic", "downgrade", revision])
    elif command == "show":
        print("当前数据库版本:")
        run_command(["alembic", "current"])
    else:
        print(f"未知命令: {command}")
        print(__doc__)
        sys.exit(1)

async def init_database():
    """初始化数据库表"""
    try:
        from app.model import create_table
        await create_table()
        print("数据库表初始化完成！")
    except Exception as e:
        print(f"初始化失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
