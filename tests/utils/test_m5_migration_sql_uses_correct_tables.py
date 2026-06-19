"""
回归测试:M5 迁移 SQL 必须引用模型的实际 __tablename__,不能写错表名。

背景:之前 MANUAL_MIGRATION.sql 写成 'interface_case_step_content_result',
但实际模型 InterfaceCaseContentResult.__tablename__ = 'interface_case_content_result',
用户照文档跑迁移会漏掉结果表,ORM 读 int 列触发 LookupError。
"""
import re
from pathlib import Path

import pytest

from app.model.interfaceAPIModel.contents.interfaceCaseContentsModel import (
    InterfaceCaseContents,
)
from app.model.interfaceAPIModel.interfaceResultModel import (
    InterfaceCaseContentResult,
)
from tests.croe.interface._bug_ids import BUG_M5


@pytest.fixture
def bug_m5_marker():
    return BUG_M5


def _read_migration_sql() -> str:
    """读 MANUAL_MIGRATION.sql 全文。"""
    repo_root = Path(__file__).resolve().parents[2]
    sql_path = repo_root / "docs" / "MANUAL_MIGRATION.sql"
    return sql_path.read_text(encoding="utf-8")


def _extract_m5_section(sql: str) -> str:
    """从全文抽出 M5 章节(从 'M5 追加' 到文件末尾)。"""
    # 从 '-- M5 追加:' 一直取到末尾
    idx = sql.find("-- M5 追加:")
    assert idx >= 0, "M5 章节未找到, 文档结构被破坏"
    return sql[idx:]


@pytest.mark.unit
def test_m5_migration_targets_contents_table(bug_m5_marker):
    """[BUG-M5] M5 迁移 SQL 必须 ALTER/UPDATE InterfaceCaseContents 对应的表。"""
    expected = InterfaceCaseContents.__tablename__
    section = _extract_m5_section(_read_migration_sql())
    assert f"ALTER TABLE {expected}" in section, (
        f"[{BUG_M5}] M5 章节应有 `ALTER TABLE {expected}`, 实际未找到"
    )
    assert f"UPDATE {expected}" in section, (
        f"[{BUG_M5}] M5 章节应有 `UPDATE {expected} SET content_type = ...`, 实际未找到"
    )


@pytest.mark.unit
def test_m5_migration_targets_result_table(bug_m5_marker):
    """[BUG-M5] M5 迁移 SQL 必须 ALTER/UPDATE InterfaceCaseContentResult 对应的表。

    不能写成 'interface_case_step_content_result' (多 _step_, 跟 contents 表重名),
    那会导致用户照文档跑迁移漏掉结果表。
    """
    expected = InterfaceCaseContentResult.__tablename__
    section = _extract_m5_section(_read_migration_sql())
    assert f"ALTER TABLE {expected}" in section, (
        f"[{BUG_M5}] M5 章节应有 `ALTER TABLE {expected}`, "
        f"实际未找到 — 这是 P0:用户照文档跑会漏掉结果表, ORM 读 int 触发 LookupError"
    )
    assert f"UPDATE {expected}" in section, (
        f"[{BUG_M5}] M5 章节应有 `UPDATE {expected} SET content_type = ...`, 实际未找到"
    )


@pytest.mark.unit
def test_m5_migration_no_wrong_step_content_result_table(bug_m5_marker):
    """[BUG-M5] M5 迁移 SQL 不能再出现 'interface_case_step_content_result' (错表名)。"""
    section = _extract_m5_section(_read_migration_sql())
    assert "interface_case_step_content_result" not in section, (
        f"[{BUG_M5}] M5 章节出现错表名 'interface_case_step_content_result', "
        f"实际模型表名是 'interface_case_content_result' (没有 _step_)"
    )
