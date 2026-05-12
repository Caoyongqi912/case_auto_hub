#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/5/7
# @Author : cyq
# @File : insert_test_data
# @Software: PyCharm
# @Desc: 使用 MCP MySQL Server 插入测试数据

import asyncio
import random
import string
from datetime import datetime
import aiomysql


def random_string(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def random_action():
    actions = [
        f"点击 {random_string(8)} 按钮",
        f"输入 {random_string(8)} 到 {random_string(8)} 字段",
        f"验证 {random_string(8)} 显示正确",
        f"等待 {random_string(8)} 秒",
        f"滚动到 {random_string(8)} 元素",
        f"清除 {random_string(8)} 字段内容",
        f"提交 {random_string(8)} 表单",
        f"打开 {random_string(8)} 链接",
        f"关闭 {random_string(8)} 弹窗",
        f"选择 {random_string(8)} 选项",
    ]
    return random.choice(actions)


def random_expected_result():
    results = [
        f"页面显示 {random_string(8)}",
        f"{random_string(8)} 操作成功",
        f"{random_string(8)} 显示预期内容",
        f"{random_string(8)} 状态正确",
        f"{random_string(8)} 数据验证通过",
        f"{random_string(8)} 元素可见",
        f"{random_string(8)} 加载完成",
    ]
    return random.choice(results)


async def main():
    pool = await aiomysql.create_pool(
        host="127.0.0.1",
        port=3306,
        user="root",
        password="sdkjfhsdkjhfsdkhfksd",
        db="caseHub",
        autocommit=False,
        charset="utf8mb4"
    )

    module_ids = [8, 9]
    admin_id = 9
    admin_name = "admin"
    project_id = 1

    case_count = 1000
    batch_size = 100

    print(f"开始插入 {case_count} 条测试用例...")

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            for batch_num in range(0, case_count, batch_size):
                cases = []
                for i in range(batch_num, min(batch_num + batch_size, case_count)):
                    case_name = f"测试用例_{i + 1}_{random_string(8)}"
                    case_tag = random.choice(["冒烟", "回归", "功能", "集成", "UI"])
                    case_level = random.choice(["P0", "P1", "P2", "P3"])
                    case_type = random.randint(1, 5)
                    module_id = random.choice(module_ids)
                    case_mark = f"自动化生成测试用例 #{i + 1}"
                    case_setup = f"前置条件: {random_string(20)}"

                    cases.append((
                        case_name, case_tag, case_setup, case_mark, 0,
                        module_id, project_id, None,
                        admin_id, admin_name, admin_id, admin_name,
                        case_level, case_type
                    ))

                insert_case_sql = """
                    INSERT INTO test_case 
                    (case_name, case_tag, case_setup, case_mark, is_common,
                     module_id, project_id, uid, create_time, update_time,
                     updater, updaterName, creator, creatorName,
                     case_level, case_type)
                    VALUES 
                    (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s, %s, %s, %s, %s, %s)
                """
                await cur.executemany(insert_case_sql, cases)
                await conn.commit()

                case_ids = []
                await cur.execute("SELECT LAST_INSERT_ID() - %s + 1 AS start_id, LAST_INSERT_ID() AS last_id", (len(cases) - 1,))
                row = await cur.fetchone()
                start_id = row[0]
                last_id = row[1]
                
                for idx in range(len(cases)):
                    case_ids.append(start_id + idx)

                await cur.execute("SELECT id FROM test_case WHERE id >= %s AND id <= %s LIMIT %s", (start_id, last_id, len(cases)))
                case_ids = [row[0] for row in await cur.fetchall()]

                sub_steps = []
                for case_id in case_ids:
                    step_count = random.randint(1, 3)
                    for step_order in range(1, step_count + 1):
                        sub_steps.append((
                            case_id,
                            random_action(),
                            random_expected_result(),
                            step_order,
                            None,
                            admin_id, admin_name, admin_id, admin_name
                        ))

                insert_step_sql = """
                    INSERT INTO case_sub_step 
                    (test_case_id, action, expected_result, `order`, 
                     uid, create_time, update_time,
                     creator, creatorName, updater, updaterName)
                    VALUES 
                    (%s, %s, %s, %s, %s, NOW(), NOW(), %s, %s, %s, %s)
                """
                await cur.executemany(insert_step_sql, sub_steps)
                await conn.commit()

                print(f"  已完成: {min(batch_num + batch_size, case_count)}/{case_count} 条用例, "
                      f"步骤: {len(sub_steps)} 条")

                await cur.execute("SELECT COUNT(*) FROM test_case")
                total_cases = (await cur.fetchone())[0]
                await cur.execute("SELECT COUNT(*) FROM case_sub_step")
                total_steps = (await cur.fetchone())[0]

    pool.close()
    await pool.wait_closed()

    print(f"\n插入完成!")
    print(f"总计: {case_count} 条测试用例")
    total_cases = 0
    total_steps = 0
    print(f"数据库统计: test_case = {total_cases}, case_sub_step = {total_steps}")

if __name__ == "__main__":
    asyncio.run(main())