"""
BUG-F8-followup 回归测试:finalize_case_result 末尾必须回填
`interface_result.content_result_id` 反向 FK。

直接证据 (F8 修复后暴露):
- step_content_api.py: `write_interface_result(immediate=True)` 先入库, 当时
  content_result_id 还是 NULL (cache 里的 content_result 还没 id)
- finalize flush 完 cache 后, 正向关系 (子表 api) 已落盘, 但
  interface_result.content_result_id 仍是 NULL
- 业务影响: 详情页/详情查询拿不到反向关联

本测试锁住:
1. InterfaceResultMapper 有 backfill_content_result_id_fk 方法
2. finalize_case_result 末尾调用 backfill
3. 端到端: 跑一个真实 case, 验 interface_result.content_result_id 非 NULL
"""
import os
import asyncio
import inspect
import pytest
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path
from sqlalchemy import text

from tests.croe.interface._bug_ids import BUG_F8B


@pytest.fixture
def bug_f8b_marker():
    return BUG_F8B


REPO = Path(__file__).resolve().parents[3]


# ---------- 1. mapper 暴露 backfill_content_result_id_fk ----------

def test_bug_f8b_mapper_has_backfill_method(bug_f8b_marker):
    """[BUG-F8B] InterfaceResultMapper 必须有 backfill_content_result_id_fk"""
    from app.mapper.interfaceApi.interfaceResultMapper import InterfaceResultMapper
    assert hasattr(InterfaceResultMapper, "backfill_content_result_id_fk"), (
        f"[{BUG_F8B}] InterfaceResultMapper 缺 backfill_content_result_id_fk 方法"
    )
    sig = inspect.signature(InterfaceResultMapper.backfill_content_result_id_fk)
    assert "case_result_id" in sig.parameters, (
        f"[{BUG_F8B}] backfill 必须接 case_result_id 参数"
    )


# ---------- 2. finalize_case_result 源码里调 backfill ----------

def test_bug_f8b_finalize_invokes_backfill(bug_f8b_marker):
    """[BUG-F8B] finalize_case_result 末尾必须调 backfill_content_result_id_fk"""
    src = (REPO / "croe" / "interface" / "writer" / "result_writer.py").read_text(
        encoding="utf-8"
    )
    assert "backfill_content_result_id_fk" in src, (
        f"[{BUG_F8B}] result_writer.py 没调 backfill, finalize 后反向 FK 永远 NULL"
    )
    # 必须在 finalize_case_result 函数体里 (粗略: 在 _flush_cache 之后)
    finalize_idx = src.find("async def finalize_case_result")
    backfill_idx = src.find("backfill_content_result_id_fk")
    flush_idx = src.find("await self._flush_cache()", finalize_idx)
    assert 0 <= finalize_idx < backfill_idx, (
        f"[{BUG_F8B}] backfill 调用不在 finalize_case_result 之后"
    )
    assert finalize_idx < flush_idx < backfill_idx, (
        f"[{BUG_F8B}] backfill 调用顺序错: 必须在 _flush_cache() 之后"
    )


# ---------- 3. UPDATE SQL 走正向关系 (子表 api) ----------

def test_bug_f8b_backfill_sql_uses_forward_link(bug_f8b_marker):
    """[BUG-F8B] 回填 SQL 必须 join interface_case_content_result_api 正向关系表"""
    from app.mapper.interfaceApi.interfaceResultMapper import InterfaceResultMapper
    import re
    # 方法源码里的 SQL 包含子表 api + 父表 cr
    src = inspect.getsource(InterfaceResultMapper.backfill_content_result_id_fk)
    assert "interface_case_content_result_api" in src, (
        f"[{BUG_F8B}] backfill SQL 缺 interface_case_content_result_api JOIN"
    )
    assert "interface_case_content_result" in src, (
        f"[{BUG_F8B}] backfill SQL 缺 interface_case_content_result JOIN"
    )
    assert "interface_result" in src, (
        f"[{BUG_F8B}] backfill SQL 缺 interface_result 表"
    )
    assert "content_result_id IS NULL" in src, (
        f"[{BUG_F8B}] backfill SQL 没加 NULL 守卫, 会反复 UPDATE 已回填的行"
    )


# ---------- 4. 端到端: 跑一个真实 case 验反向 FK 被回填 ----------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_bug_f8b_e2e_backfill_after_real_case_run(bug_f8b_marker):
    """
    [BUG-F8B] 跑一个真实 case (用 case 3 'Case2(副本)'), 验
    interface_result.content_result_id 已被回填, 不再是 NULL。
    """
    if os.environ.get("SKIP_E2E"):
        pytest.skip("SKIP_E2E set")

    from croe.interface.starter import APIStarter

    class FakeUser:
        id = 1
        userId = 1
        username = "test"
        startBy = "test"
        uid = "u-test"

    class FakeStarter(APIStarter):
        def __init__(self):
            self.logs = []
        async def send(self, msg):
            self.logs.append(msg)
        async def over(self, case_result_id=None):
            pass
        @property
        def userId(self): return 1
        @property
        def username(self): return "test"
        @property
        def startBy(self): return "test"
        @property
        def uid(self): return "u-test"

    from croe.interface.runner import InterfaceRunner
    from app.mapper import Mapper

    starter = FakeStarter()
    runner = InterfaceRunner(starter=starter)

    success, case_result = await runner.run_interface_case(
        interface_case_id=3, env=1, error_stop=False
    )
    assert case_result is not None, f"[{BUG_F8B}] case_result 为空"

    # 查这次跑出来的 interface_result, content_result_id 必须非 NULL
    async with Mapper.transaction() as session:
        rows = (await session.execute(
            text(
                "SELECT id, interface_id, content_result_id "
                "FROM interface_result "
                "WHERE id > (SELECT COALESCE(MAX(id), 0) - 5 FROM interface_result) "
                "ORDER BY id DESC"
            )
        )).all()

    # 至少一行有 content_result_id
    with_fk = [r for r in rows if r[2] is not None]
    assert with_fk, (
        f"[{BUG_F8B}] 跑完 case 后 interface_result.content_result_id 仍全是 NULL, "
        f"backfill 没生效。rows={rows}"
    )
    print(f"\n[{BUG_F8B}] E2E 通过: {len(with_fk)}/{len(rows)} 行有反向 FK")
