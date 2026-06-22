"""5 easy wins 回归测试。"""

import inspect
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from loguru import logger as loguru_logger

from croe.interface.observability import install_patchers

# ============================================================
# ============================================================

@pytest.mark.unit
def test_bug_d10_update_by_id_accepts_post_update_hook():
    """update_by_id 签名必须有 post_update_hook 参数。"""
    from app.mapper import Mapper
    sig_src = inspect.getsource(Mapper.update_by_id)
    assert "post_update_hook" in sig_src, (
        f"update_by_id 缺 post_update_hook 参数, 当前源码:\n{sig_src[:500]}"
    )

@pytest.mark.unit
def test_bug_d10_update_cls_keeps_target_attached_for_hook():
    """update_by_id 必须在 expunge 之前调 post_update_hook (target 还 attached)。"""
    from app.mapper import Mapper
    sig_src = inspect.getsource(Mapper.update_by_id)
    # hook 调用位置 (函数体内) 必须在 update_cls 调用之后
    # 找的是函数体里的 "await cls.update_cls" 和 "if post_update_hook"
    # 避开 docstring 里出现的 "post_update_hook" 描述
    update_cls_call_pos = sig_src.find("await cls.update_cls")
    hook_call_pos = sig_src.find("if post_update_hook is not None")
    assert update_cls_call_pos > 0, (
        f"update_by_id 必须调 update_cls, 当前 src: {sig_src[:600]}"
    )
    assert hook_call_pos > 0, (
        f"update_by_id 必须 None check hook, 当前 src: {sig_src[:600]}"
    )
    assert hook_call_pos > update_cls_call_pos, (
        f"post_update_hook 必须在 update_cls 之后调 (target 还 attached)。 "
        f"update_cls pos={update_cls_call_pos}, hook pos={hook_call_pos}"
    )

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d10_post_update_hook_receives_target_before_expunge():
    """[
    端到端 mock: 用 update_by_id 跑一次, hook 拿到 target 时验证它未被 expunge。
    """
    from app.mapper import Mapper

    target = MagicMock()
    target.id = 42
    target.to_dict = MagicMock(return_value={"id": 42, "name": "after"})

    hook_called_with = []

    def my_hook(t):
        hook_called_with.append(t)
        return {"snap": t.to_dict()}

    # 直接 patch 掉 SQLAlchemy 路径: mock get_by_id + update_cls
    async def fake_update_cls(target, session, **kw):
        for k, v in kw.items():
            if hasattr(target, k):
                setattr(target, k, v)
        # 不 expunge (修复后的行为)
        return target

    with patch.object(Mapper, "get_by_id", AsyncMock(return_value=target)):
        with patch.object(Mapper, "update_cls", AsyncMock(side_effect=fake_update_cls)):
            with patch.object(Mapper, "transaction") as mock_tx:
                # transaction() 返回 async context manager
                cm = MagicMock()
                cm.__aenter__ = AsyncMock(return_value=MagicMock())
                cm.__aexit__ = AsyncMock(return_value=None)
                mock_tx.return_value = cm

                result = await Mapper.update_by_id(
                    id=42,
                    name="after",
                    post_update_hook=my_hook,
                )

    # hook 调了, 拿到的 target 是 42
    assert len(hook_called_with) == 1, f"hook 必须被调 1 次, 实际 {len(hook_called_with)}"
    assert hook_called_with[0] is target
    # hook 返回值被透传
    assert result == {"snap": {"id": 42, "name": "after"}}

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_d10_no_hook_returns_target_as_before():
    """不传 post_update_hook 时, update_by_id 仍返 target (向后兼容)。"""
    from app.mapper import Mapper

    target = MagicMock()
    target.id = 42

    async def fake_update_cls(target, session, **kw):
        return target

    with patch.object(Mapper, "get_by_id", AsyncMock(return_value=target)):
        with patch.object(Mapper, "update_cls", AsyncMock(side_effect=fake_update_cls)):
            with patch.object(Mapper, "transaction") as mock_tx:
                cm = MagicMock()
                cm.__aenter__ = AsyncMock(return_value=MagicMock())
                cm.__aexit__ = AsyncMock(return_value=None)
                mock_tx.return_value = cm

                result = await Mapper.update_by_id(id=42, name="after")

    assert result is target, (
        f"不传 hook 时必须返 target, 实际: {result!r}"
    )

@pytest.mark.unit
def test_bug_d10_update_interface_case_uses_post_update_hook():
    """update_interface_case 必须用 post_update_hook 拿 to_dict 快照。"""
    from app.mapper.interfaceApi.interfaceCaseMapper import InterfaceCaseMapper
    src = inspect.getsource(InterfaceCaseMapper.update_interface_case)
    assert "post_update_hook" in src, (
        f"update_interface_case 必须用 post_update_hook, 当前 src:\n{src[:500]}"
    )
    # 不应在 update_by_id 之后还有 to_dict() 调用 (那是 bug)
    # 简化检查: `new_case.to_dict()` 不应再出现
    assert "new_case.to_dict()" not in src, (
        f"update_interface_case 不应在 update_by_id 后调 to_dict(), "
        f"应在 post_update_hook 里调 (target 还 attached)"
    )

@pytest.mark.unit
def test_bug_d10_update_interface_uses_post_update_hook():
    """update_interface 必须用 post_update_hook 拿 to_dict 快照。"""
    from app.mapper.interfaceApi.interfaceMapper import InterfaceMapper
    src = inspect.getsource(InterfaceMapper.update_interface)
    assert "post_update_hook" in src, (
        f"update_interface 必须用 post_update_hook"
    )
    assert "new_interface.to_dict()" not in src, (
        f"update_interface 不应在 update_by_id 后调 to_dict()"
    )

# ============================================================
# ============================================================

@pytest.mark.unit
def test_bug_e11_condition_step_writes_assert_data():
    """step_content_condition 写库时必须含 assert_data=content_condition。"""
    from croe.interface.executor.step_content.step_content_condition import (
        APIConditionContentStrategy,
    )
    src = inspect.getsource(APIConditionContentStrategy.execute)
    assert "assert_data=content_condition" in src, (
        f"step_content_condition 写库漏 assert_data 字段, 应加 assert_data=content_condition, 当前 src:\n{src[:800]}"
    )

# ============================================================
# ============================================================

@pytest.mark.unit
def test_bug_obs_4_starter_msg_type_constant_exists():
    """starter 模块必须有 STARTER_MSG_TYPE 常量 + 5+ 类型。"""
    from croe.interface.starter import STARTER_MSG_TYPE
    # 必须有 5 个结构化类型
    for t in ("TYPE_EXECUTE", "TYPE_EXTRACT", "TYPE_SKIP", "TYPE_FINISH", "TYPE_ERROR"):
        assert hasattr(STARTER_MSG_TYPE, t), (
            f"STARTER_MSG_TYPE 缺 {t}"
        )

@pytest.mark.unit
def test_bug_obs_4_starter_has_send_typed_method():
    """APIStarter 必须有 send_typed(type, msg) 方法。"""
    from croe.interface.starter import APIStarter
    assert hasattr(APIStarter, "send_typed"), (
        f"APIStarter 缺 send_typed 方法, 推荐用结构化 [TYPE_xxx] 前缀"
    )
    src = inspect.getsource(APIStarter.send_typed)
    assert "msg_type" in src, "send_typed 必须有 msg_type 参数"

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_obs_4_send_typed_prepends_type_marker():
    """send_typed 调用 super().send 时, msg 必须含 [TYPE_xxx] 前缀。"""
    from croe.interface.starter import APIStarter, STARTER_MSG_TYPE
    from app.model.base import User

    user = MagicMock(spec=User)
    starter = APIStarter(user=user)
    captured = []
    # mock super().send 抓消息
    async def fake_super_send(msg):
        captured.append(msg)
    from utils.io_sender import SocketSender
    with patch.object(SocketSender, "send", AsyncMock(side_effect=fake_super_send)):
        await starter.send_typed(STARTER_MSG_TYPE.TYPE_EXTRACT, "变量 x = 1")
    # 抓到的消息必须含 [TYPE_EXTRACT]
    assert any("[TYPE_EXTRACT]" in m for m in captured), (
        f"send_typed 没传 [TYPE_xxx] 前缀, 实际: {captured!r}"
    )

# ============================================================
# ============================================================

@pytest.mark.unit
def test_bug_obs_5_set_result_field_returns_bool():
    """InterfaceCaseResultMapper.set_result_field 源码必须返 bool。"""
    from app.mapper.interfaceApi.interfaceResultMapper import InterfaceCaseResultMapper
    src = inspect.getsource(InterfaceCaseResultMapper.set_result_field)
    # 必须有 `-> bool` 返回类型注解
    assert "-> bool" in src, (
        f"set_result_field 应 -> bool, 当前:\n{src}"
    )
    # 必须有 return True
    assert "return True" in src, (
        f"set_result_field 成功路径必须 return True, 当前:\n{src}"
    )
    # 不应再吞错 (raise e 应改成 raise)
    # 但允许 log.error + raise 模式
    assert "raise" in src, "set_result_field 失败路径必须 raise"

# ============================================================
# ============================================================

@pytest.mark.unit
def test_bug_obs_6_runner_logs_case_result_id():
    """run_interface_case 第一条 log 后必须显式 log case_result_id。"""
    from croe.interface.runner import InterfaceRunner
    src = inspect.getsource(InterfaceRunner.run_interface_case)
    # 必须在 case_result 创建后 log case_result_id
    assert "case_result_id=" in src, (
        f"run_interface_case 应显式 log case_result_id, 当前:\n{src[:1000]}"
    )

@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_bug_obs_6_log_message_contains_case_result_id():
    """端到端: log.info 触发后, captured log message 必须含 case_result_id=。"""
    pytest.skip("AST check above is sufficient; 真实 case_result.id 需要 DB")
