"""BUG-E10 回归测试: step_content_db 异常应被 try/except 兜住, 跟 step_content_script 一致。"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from croe.interface.executor.step_content.step_content_db import APIDBContentStrategy
from enums import StepStatusEnum
from tests.croe.interface._bug_ids import BUG_E10

REPO_ROOT = Path(__file__).resolve().parents[3]

def _db_src() -> str:
    return (REPO_ROOT / "croe/interface/executor/step_content/step_content_db.py").read_text(encoding="utf-8")

@pytest.fixture
def bug_e10_marker():
    return BUG_E10

# --------------------------------------------------------------------------- #
# E10.1 - 源码层: try/except 应存在
# --------------------------------------------------------------------------- #

@pytest.mark.unit
def test_bug_e10_try_except_in_db_strategy(bug_e10_marker):
    """[BUG-E10] step_content_db.py 应有 try/except 包裹 db_script.invoke。"""
    src = _db_src()
    # db_script.invoke 必须在 try 块里
    try_idx = src.find("try:")
    invoke_idx = src.find("db_script.invoke(")
    except_idx = src.find("except Exception")
    assert try_idx != -1 and invoke_idx != -1 and except_idx != -1, (
        f"[{BUG_E10}] step_content_db.py 缺 try/except 包裹 db_script.invoke, "
        "数据库异常会拖垮整个 step。"
    )
    assert try_idx < invoke_idx < except_idx, (
        f"[{BUG_E10}] try/except 顺序不对, 应 try 在 invoke 前, except 在 invoke 后。"
    )

# --------------------------------------------------------------------------- #
# E10.2 / E10.3 - 行为层: 异常被兜住, success=False, 仍写 result
# --------------------------------------------------------------------------- #

def _build_ctx(content_id=1, db_id=1, sql_text="SELECT 1", sql_extracts=None):
    ctx = MagicMock()
    ctx.index = 1
    ctx.content = MagicMock()
    ctx.content.id = content_id
    ctx.content.target_id = content_id
    ctx.content.resolved_content_name = "db_step"
    ctx.content.content_desc = "desc"
    ctx.execution_context = MagicMock()
    ctx.execution_context.case_result = MagicMock()
    ctx.execution_context.case_result.id = 100
    ctx.execution_context.case_result.success_num = 0
    ctx.execution_context.task_result = None
    ctx.starter = MagicMock()
    ctx.starter.send = AsyncMock()
    ctx.variable_manager = MagicMock()
    ctx.variable_manager.trans = AsyncMock(return_value=sql_text)
    ctx.variable_manager.add_vars = AsyncMock()
    ctx.result_writer = MagicMock()
    ctx.result_writer.update_case_progress = AsyncMock()
    return ctx

@pytest.mark.asyncio
@pytest.mark.unit
async def test_bug_e10_db_invoke_exception_does_not_propagate(bug_e10_marker):
    """[BUG-E10] db_script.invoke 抛异常: step 不应 propagate, 应返回 False。"""
    ctx = _build_ctx()

    fake_content_sql = MagicMock()
    fake_content_sql.db_id = 1
    fake_content_sql.sql_text = "SELECT 1"
    fake_content_sql.sql_extracts = None

    fake_db_config = MagicMock()
    fake_db_config.db_type = "mysql"
    fake_db_config.config = {"host": "x"}

    with patch("croe.interface.executor.step_content.step_content_db.DBExecuteMapper.get_by_id",
               AsyncMock(return_value=fake_content_sql)), \
         patch("croe.interface.executor.step_content.step_content_db.DbConfigMapper.get_by_id",
               AsyncMock(return_value=fake_db_config)):
        # 强制 db_script.invoke 抛异常
        with patch("croe.interface.executor.step_content.step_content_db.ExecDBScript") as MockEDS:
            instance = MockEDS.return_value
            instance.invoke = AsyncMock(side_effect=ConnectionError("DB down"))
            with patch("croe.interface.executor.step_content.step_content_db.InterfaceContentStepResultMapper.insert_result",
                       AsyncMock()) as mock_insert:
                strategy = APIDBContentStrategy(MagicMock())
                # 关键: step execute 不应抛
                ret = await strategy.execute(ctx)
                assert ret is False, (
                    f"[{BUG_E10}] 异常时 step 应返回 False (success=False), 实际 {ret}"
                )
                # WARNING 留痕
                assert mock_insert.call_count == 1, "应仍调一次 insert_result (写 FAIL 状态)"
                call_kwargs = mock_insert.call_args.kwargs
                assert call_kwargs["result"] is False, "result=False 应写入"
                assert call_kwargs["status"] == StepStatusEnum.FAIL, "status='FAIL' 应写入"

@pytest.mark.asyncio
@pytest.mark.unit
async def test_bug_e10_db_invoke_success_path(bug_e10_marker):
    """[BUG-E10] db_script.invoke 正常: step 返回 True, status=SUCCESS, 变量写入。"""
    ctx = _build_ctx()

    fake_content_sql = MagicMock()
    fake_content_sql.db_id = 1
    fake_content_sql.sql_text = "SELECT 1"
    fake_content_sql.sql_extracts = None

    fake_db_config = MagicMock()
    fake_db_config.db_type = "mysql"
    fake_db_config.config = {"host": "x"}

    with patch("croe.interface.executor.step_content.step_content_db.DBExecuteMapper.get_by_id",
               AsyncMock(return_value=fake_content_sql)), \
         patch("croe.interface.executor.step_content.step_content_db.DbConfigMapper.get_by_id",
               AsyncMock(return_value=fake_db_config)):
        with patch("croe.interface.executor.step_content.step_content_db.ExecDBScript") as MockEDS:
            instance = MockEDS.return_value
            instance.invoke = AsyncMock(return_value={"x": 1})
            with patch("croe.interface.executor.step_content.step_content_db.InterfaceContentStepResultMapper.insert_result",
                       AsyncMock()) as mock_insert:
                strategy = APIDBContentStrategy(MagicMock())
                ret = await strategy.execute(ctx)
                assert ret is True
                # 成功路径: variable_manager.add_vars 应被调用
                ctx.variable_manager.add_vars.assert_called_once_with({"x": 1})
                call_kwargs = mock_insert.call_args.kwargs
                assert call_kwargs["result"] is True
                assert call_kwargs["status"] == StepStatusEnum.SUCCESS
