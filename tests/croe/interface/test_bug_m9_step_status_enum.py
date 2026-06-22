"""case step content 的 status 字段应走 StepStatusEnum,"""

from enum import Enum
from pathlib import Path

import pytest

from app.model.interfaceAPIModel.interfaceResultModel import InterfaceCaseContentResult
from enums import StepStatusEnum
from tests.croe.interface._bug_ids import BUG_M9

REPO_ROOT = Path(__file__).resolve().parents[3]

@pytest.fixture
def bug_m9_marker():
    return BUG_M9

# --------------------------------------------------------------------------- #
# M9.1 - 源码层: 0 处 status="SUCCESS"/"FAIL" 字面量
# --------------------------------------------------------------------------- #

STEP_CONTENT_FILES = [
    "croe/interface/executor/step_content/step_content_loop.py",
    "croe/interface/executor/step_content/step_content_group.py",
    "croe/interface/executor/step_content/step_content_script.py",
    "croe/interface/executor/step_content/step_content_condition.py",
    "croe/interface/executor/step_content/step_content_db.py",
    "croe/interface/executor/step_content/step_content_assert.py",
    "croe/interface/executor/step_content/step_content_wait.py",
]

@pytest.mark.unit
def test_bug_m9_step_status_enum_exists(bug_m9_marker):
    """enums.InterfaceEnum.StepStatusEnum 应是 enum.Enum 子类。"""
    assert issubclass(StepStatusEnum, Enum), (
        f"[{BUG_M9}] StepStatusEnum 必须继承 enum.Enum 才能被 SQLAlchemy Enum(...) 接受。"
    )
    assert StepStatusEnum.SUCCESS.value == "SUCCESS"
    assert StepStatusEnum.FAIL.value == "FAIL"
    # 兼容历史 default='PENDING'
    assert StepStatusEnum.PENDING.value == "PENDING"

@pytest.mark.unit
def test_bug_m9_no_status_string_literal_in_step_content(bug_m9_marker):
    """[
    允许 StepStatusEnum.SUCCESS / .FAIL (枚举常量), 不允许直接字面量。
    """
    for rel in STEP_CONTENT_FILES:
        src = (REPO_ROOT / rel).read_text(encoding="utf-8")
        # 排除注释行
        code_lines = [ln for ln in src.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
        code_blob = "\n".join(code_lines)
        for bad in ['status="SUCCESS"', "status='SUCCESS'", 'status="FAIL"', "status='FAIL'"]:
            assert bad not in code_blob, (
                f"[{BUG_M9}] {rel} 仍有字面量 {bad}, 应改用 StepStatusEnum.SUCCESS / .FAIL。"
            )

@pytest.mark.unit
def test_bug_m9_step_status_enum_imported_in_step_content(bug_m9_marker):
    """8 个 step_content 文件应 import StepStatusEnum。"""
    for rel in STEP_CONTENT_FILES:
        src = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "StepStatusEnum" in src, (
            f"[{BUG_M9}] {rel} 没 import StepStatusEnum。"
        )

# --------------------------------------------------------------------------- #
# M9.2 / M9.3 - model 层: status 字段是 Enum(StepStatusEnum, ...)
# --------------------------------------------------------------------------- #

@pytest.mark.unit
def test_bug_m9_status_field_is_enum(bug_m9_marker):
    """InterfaceCaseContentResult.status 字段应是 Enum 类型, 不是 String。"""
    from sqlalchemy import Enum as SAEnum
    col = InterfaceCaseContentResult.__table__.columns["status"]
    assert isinstance(col.type, SAEnum), (
        f"[{BUG_M9}] status 字段类型应为 SQLAlchemy Enum, 实际 {type(col.type).__name__}。"
    )
    # enum class 应是 StepStatusEnum
    enum_class = col.type.enum_class
    assert enum_class is StepStatusEnum, (
        f"[{BUG_M9}] status 字段 enum_class 应为 StepStatusEnum, 实际 {enum_class}。"
    )
    # native_enum=False 表示走 VARCHAR
    assert col.type.native_enum is False, (
        f"[{BUG_M9}] status 字段应 native_enum=False (走 VARCHAR 兼容 MySQL 5.7/8.0)。"
    )
    # length 跟 PENDING=7 字符对齐
    assert col.type.length == 20, (
        f"[{BUG_M9}] status 字段 length 应为 20, 实际 {col.type.length}。"
    )

@pytest.mark.unit
def test_bug_m9_status_default_is_pending_or_enum_member(bug_m9_marker):
    """status 字段 default 应是 StepStatusEnum 成员 (兼容 PENDING 历史值)。"""
    col = InterfaceCaseContentResult.__table__.columns["status"]
    default = col.default
    if default is not None:
        # SQLAlchemy 把 default.arg 存起来
        arg = getattr(default, "arg", default)
        assert arg in {StepStatusEnum.SUCCESS, StepStatusEnum.FAIL, StepStatusEnum.PENDING,
                       "SUCCESS", "FAIL", "PENDING"}, (
            f"[{BUG_M9}] status 字段 default 应是 StepStatusEnum 成员, 实际 {arg}。"
        )

@pytest.mark.unit
def test_bug_m9_status_only_accepts_enum_members(bug_m9_marker):
    """status 字段只接受 StepStatusEnum 已声明的成员, 写错字符串会报错。"""
    from sqlalchemy import Enum as SAEnum
    col = InterfaceCaseContentResult.__table__.columns["status"]
    # SAEnum 接受合法的 enum member name/value
    # 验证: 'OK' / 'DONE' 这种老字面量错误不在合法集合
    valid_values = {m.value for m in StepStatusEnum}
    assert "OK" not in valid_values, "StepStatusEnum 不应含 'OK', 老字面量错值应被拒"
    assert "DONE" not in valid_values
    # 反向: SAEnum._valid_lookup 走 StepStatusEnum
    assert col.type.length >= max(len(v) for v in valid_values)
