"""app/model/playUI/* 模型层单元测试覆盖"""

import datetime

import pytest
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Text

from app.model.playUI import (
    PlayCase, PlayCaseResult, PlayCaseVariables, PlayTask, PlayTaskResult,
)
from app.model.playUI.playAssociation import PlayCaseStepContentAssociation
from app.model.playUI.playStepContent import PlayStepContent
from app.model.playUI.PlayResult import PlayStepContentResult

# --------------------------------------------------------------------------- #
# PlayCase
# --------------------------------------------------------------------------- #

class TestPlayCase:
    """PlayCase 模型测试。"""

    def test_tablename(self):
        """tablename 必须是 play_case (跟 schema 对齐)。"""
        assert PlayCase.__tablename__ == "play_case"

    def test_required_columns(self):
        """必有字段: title / description / status / level。"""
        cols = {c.key for c in PlayCase.__table__.columns}
        assert "title" in cols
        assert "description" in cols
        assert "status" in cols
        assert "level" in cols
        assert "module_id" in cols
        assert "project_id" in cols

    def test_desc_truncates_long_description(self):
        """desc property 在 description>10 字符时截断为前 10 字符 + ...。"""
        pc = PlayCase(title="t", description="a" * 20, status="DONE", level="P1")
        assert pc.desc == "a" * 10 + "..."

    def test_desc_short_description_no_truncate(self):
        """desc property 在 description<=10 字符时不截断。"""
        pc = PlayCase(title="t", description="short", status="DONE", level="P1")
        assert pc.desc == "short"

    def test_repr_format(self):
        """__repr__ 应包含 title + desc。"""
        pc = PlayCase(title="登录", description="用户登录", status="DONE", level="P1")
        text = repr(pc)
        assert "登录" in text
        assert "用户登录" in text

    def test_str_format(self):
        """__str__ 格式: 【title】 description。"""
        pc = PlayCase(title="登录", description="用户登录", status="DONE", level="P1")
        text = str(pc)
        assert "登录" in text
        assert "用户登录" in text

# --------------------------------------------------------------------------- #
# PlayCaseResult (P-1-2 修复重点)
# --------------------------------------------------------------------------- #

class TestPlayCaseResult:
    """PlayCaseResult 模型 + ui_case_id property 测试 (P-1-2)。"""

    def test_tablename(self):
        """tablename 是 play_case_result。"""
        assert PlayCaseResult.__tablename__ == "play_case_result"

    def test_ui_case_Id_column_exists(self):
        """[P-1-2 修复前] SQL 列名仍是 ui_case_Id (DB 兼容, 不动 schema)。

        P-1-2 修复: Python 属性层加 ui_case_id property 别名, 不动 SQL 列。
        """
        col = PlayCaseResult.__table__.columns.get("ui_case_Id")
        assert col is not None, "DB 列名仍是 ui_case_Id (P-1-2 不动 schema)"

    def test_ui_case_id_property_reads_ui_case_Id(self):
        """[P-1-2 修复] ui_case_id property 读 ui_case_Id 字段。"""
        pcr = PlayCaseResult()
        pcr.ui_case_Id = 42
        # 通过 property 读
        assert pcr.ui_case_id == 42

    def test_ui_case_id_property_writes_ui_case_Id(self):
        """[P-1-2 修复] ui_case_id property 写时设到 ui_case_Id 字段。"""
        pcr = PlayCaseResult()
        pcr.ui_case_id = 99
        # 验证写到 ui_case_Id
        assert pcr.ui_case_Id == 99

    def test_required_columns(self):
        """必有字段: ui_case_Id (DB) / ui_case_name / starter_id / status。"""
        cols = {c.key for c in PlayCaseResult.__table__.columns}
        assert "ui_case_Id" in cols
        assert "ui_case_name" in cols
        assert "starter_id" in cols
        assert "starter_name" in cols
        assert "status" in cols
        assert "result" in cols
        assert "task_result_id" in cols

    def test_error_step_columns(self):
        """错误步骤相关字段存在: err_step / title / msg / pic。"""
        cols = {c.key for c in PlayCaseResult.__table__.columns}
        assert "ui_case_err_step" in cols
        assert "ui_case_err_step_title" in cols
        assert "ui_case_err_step_msg" in cols
        assert "ui_case_err_step_pic_path" in cols

# --------------------------------------------------------------------------- #
# PlayTask
# --------------------------------------------------------------------------- #

class TestPlayTask:
    """PlayTask 模型测试。"""

    def test_tablename(self):
        assert PlayTask.__tablename__ == "play_task"

    def test_required_columns(self):
        cols = {c.key for c in PlayTask.__table__.columns}
        assert "title" in cols
        assert "description" in cols
        assert "level" in cols
        assert "play_case_num" in cols
        assert "module_id" in cols

    def test_title_unique(self):
        """title 应 unique (P-R1 修复前的 task_runner 依赖此唯一性)。"""
        col = PlayTask.__table__.columns.get("title")
        assert col is not None
        assert col.unique is True

    def test_desc_property_truncates(self):
        """desc property 跟 PlayCase.desc 行为一致。"""
        pt = PlayTask(title="t", description="x" * 30, level="P1", module_id=1)
        assert pt.desc == "x" * 10 + "..."

# --------------------------------------------------------------------------- #
# PlayTaskResult (P-1-3 修复重点)
# --------------------------------------------------------------------------- #

class TestPlayTaskResult:
    """PlayTaskResult 模型 + rate_number Float (P-1-3) + notify dict 测试。"""

    def test_tablename(self):
        assert PlayTaskResult.__tablename__ == "play_task_result"

    def test_rate_number_is_float_column_p_1_3(self):
        """rate_number 应是 Float 列 (不是 INTEGER, 避免 85.5 → 85 截断)。"""
        col = PlayTaskResult.__table__.columns.get("rate_number")
        assert col is not None
        assert isinstance(col.type, Float), (
            f"rate_number 期望 Float, 实际 {type(col.type).__name__}"
        )

    def test_required_columns(self):
        cols = {c.key for c in PlayTaskResult.__table__.columns}
        assert "status" in cols
        assert "result" in cols
        assert "total_number" in cols
        assert "success_number" in cols
        assert "fail_number" in cols
        assert "rate_number" in cols
        assert "task_id" in cols
        assert "task_uid" in cols
        assert "run_day" in cols

    def test_notify_dict_includes_all_fields(self):
        """notify property 应返回包含所有任务结果字段的 dict。"""
        ptr = PlayTaskResult(
            id=1,
            uid="abc",
            task_id=10,
            task_uid="task-uid",
            task_name="登录任务",
            starter_name="admin",
            result="FAIL",
            total_number=10,
            success_number=7,
            fail_number=3,
            start_time=datetime.datetime(2026, 6, 21, 10, 0, 0),
            end_time=datetime.datetime(2026, 6, 21, 10, 5, 0),
            project_id=1,
        )
        notify = ptr.notify
        assert notify["task_id"] == 10
        assert notify["task_name"] == "登录任务"
        assert notify["starter"] == "admin"
        assert notify["result"] == "FAIL"
        assert notify["total"] == 10
        assert notify["success"] == 7
        assert notify["fail"] == 3
        assert notify["project_id"] == 1
        # 必有 result_id / result_uid
        assert "result_id" in notify
        assert "result_uid" in notify
        assert "start_time" in notify
        assert "end_time" in notify
        assert "use_time" in notify

    def test_repr_format(self):
        """__repr__ 应包含 task_name / task_id / run_day / status / result。"""
        ptr = PlayTaskResult(
            task_id=10,
            task_name="登录任务",
            run_day=datetime.date(2026, 6, 21),
            status="DONE",
            result="FAIL",
        )
        text = repr(ptr)
        assert "登录任务" in text or "10" in text
        assert "DONE" in text

# --------------------------------------------------------------------------- #
# PlayCaseVariables
# --------------------------------------------------------------------------- #

class TestPlayCaseVariables:
    """PlayCaseVariables 用例前置变量测试。"""

    def test_tablename(self):
        assert PlayCaseVariables.__tablename__ == "play_case_vars"

    def test_required_columns(self):
        cols = {c.key for c in PlayCaseVariables.__table__.columns}
        assert "key" in cols
        assert "value" in cols
        assert "play_case_id" in cols

    def test_key_unique(self):
        """key 列 unique (P-R3 修复前的 init_case_variables 依赖此去重)。"""
        col = PlayCaseVariables.__table__.columns.get("key")
        assert col.unique is True

    def test_repr_format(self):
        """__repr__ 应包含 key / value / play_case_id。"""
        pcv = PlayCaseVariables(key="token", value="abc", play_case_id=10)
        text = repr(pcv)
        assert "token" in text
        assert "abc" in text
        assert "10" in text

# --------------------------------------------------------------------------- #
# PlayStepContentResult
# --------------------------------------------------------------------------- #

class TestPlayStepContentResult:
    """PlayStepContentResult 步骤结果模型测试。"""

    def test_tablename(self):
        assert PlayStepContentResult.__tablename__ == "play_step_content_result"

    def test_required_columns(self):
        cols = {c.key for c in PlayStepContentResult.__table__.columns}
        assert "play_case_result_id" in cols
        assert "play_task_result_id" in cols
        assert "content_id" in cols
        assert "content_name" in cols
        assert "content_step" in cols
        assert "content_type" in cols
        assert "start_time" in cols
        assert "use_time" in cols
        assert "content_result" in cols
        # BUG 修过的 ignore_error 字段
        assert "content_ignore_error" in cols
        # 截图
        assert "content_screenshot_path" in cols
        # 父子层级
        assert "parent_result_id" in cols

    def test_repr_format(self):
        """__repr__ 包含 id / type / target_id / result。"""
        cr = PlayStepContentResult(
            content_type=1, content_target_result_id=99, content_result=True,
        )
        cr.id = 1
        text = repr(cr)
        assert "1" in text
        assert "1" in text  # type
        assert "99" in text  # target_id
        assert "True" in text or "False" in text
