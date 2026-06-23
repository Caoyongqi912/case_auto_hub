"""
2026-06-22 Round 4 - BUG-COPY-CONTENT 修复

触发: 端点 POST /interfaceCase/content/copy_step
       复制 WaitStepContent (STEP_API_WAIT) 时 500:
       AttributeError: 'WaitStepContent' object has no attribute 'target_id'

回归: tests/croe/interface/test_bug_copy_content.py
"""
import ast
import inspect
from typing import List, Set

import pytest

from app.model.interfaceAPIModel.contents import (
    APIStepContent, GroupStepContent, ConditionStepContent,
    ScriptStepContent, DBStepContent, WaitStepContent, AssertStepContent,
    LoopStepContent,
)
from enums.CaseEnum import CaseStepContentType
from tests.croe.interface._bug_ids import BUG_COPY_CONTENT


# ============================================================
# 8 个 step content 类型的 schema 锁定 (防退化)
# ============================================================

SELF_CONTAINED_CLASSES = [ScriptStepContent, WaitStepContent, AssertStepContent]
TARGET_ID_CLASSES = [APIStepContent, GroupStepContent, ConditionStepContent,
                     DBStepContent, LoopStepContent]


# ============================================================
# BUG-COPY-CONTENT: schema 层 (类型 → 是否有 target_id)
# ============================================================

class TestBugCopyContentSchema:
    """3 个 self-contained 类不能有 target_id 字段 (子表独有 = 数据自包含)"""

    @pytest.mark.parametrize("cls", SELF_CONTAINED_CLASSES)
    def test_self_contained_no_target_id(self, cls):
        """[BUG-COPY-CONTENT] self-contained 子表不应有 target_id 列 (旧版 hardcode 的字段)"""
        col_names = {c.name for c in cls.__table__.columns}
        assert "target_id" not in col_names, (
            f"[{BUG_COPY_CONTENT}] {cls.__name__} 不应有 target_id (self-contained). "
            f"实际列: {col_names}"
        )

    @pytest.mark.parametrize("cls", SELF_CONTAINED_CLASSES)
    def test_self_contained_has_unique_field(self, cls):
        """[BUG-COPY-CONTENT] self-contained 必须有独有数据字段 (wait_time/script_text/assert_list)"""
        col_names = {c.name for c in cls.__table__.columns}
        unique = {"wait_time", "script_text", "assert_list"}
        assert col_names & unique, (
            f"[{BUG_COPY_CONTENT}] {cls.__name__} 必须有 self-contained 字段 {unique} 之一, 实际: {col_names}"
        )

    @pytest.mark.parametrize("cls", TARGET_ID_CLASSES)
    def test_target_id_classes_have_target_id(self, cls):
        """[BUG-COPY-CONTENT] target_id 类必须有 target_id 列 (修复目标行为不破坏)"""
        col_names = {c.name for c in cls.__table__.columns}
        assert "target_id" in col_names, (
            f"[{BUG_COPY_CONTENT}] {cls.__name__} 应该有 target_id 列, 实际: {col_names}"
        )


# ============================================================
# BUG-COPY-CONTENT: 构造函数层 (creatorName vs username 字段名)
# ============================================================

class TestBugCopyContentConstructor:
    """BaseModel 列定义是 creatorName, 不是 username. copy_content 必须用 creatorName."""

    def test_basemodel_column_is_creator_name(self):
        """[BUG-COPY-CONTENT] BaseModel 字段是 creatorName (不是 username)

        BaseModel 是 __abstract__, 拿不到 __table__, 改用 mapper attrs 反查
        (任一具体子类的 mapper 都有基表所有列, 因为 joined-table inheritance).
        """
        from app.model.basic import BaseModel
        # 任选一个具体子类, mapper.columns 包含继承自 BaseModel 的列
        col_names = {c.key for c in APIStepContent.__mapper__.columns}
        assert "creatorName" in col_names, (
            f"[{BUG_COPY_CONTENT}] BaseModel 应该有 creatorName, 实际 mapper 列: {col_names}"
        )
        assert "username" not in col_names, (
            f"[{BUG_COPY_CONTENT}] BaseModel 不应有 username (应是 creatorName)"
        )

    @pytest.mark.parametrize("cls", SELF_CONTAINED_CLASSES)
    def test_self_contained_constructs_with_creator_name(self, cls):
        """[BUG-COPY-CONTENT] self-contained 子类必须能用 creatorName 构造"""
        kwargs = dict(creator=1, creatorName="test")
        if cls is WaitStepContent:
            kwargs["wait_time"] = 0
        elif cls is ScriptStepContent:
            kwargs["script_text"] = ""
        elif cls is AssertStepContent:
            kwargs["assert_list"] = None
        # 关键: 不能传 target_id / username
        try:
            instance = cls(**kwargs)
        except TypeError as e:
            pytest.fail(f"[{BUG_COPY_CONTENT}] {cls.__name__}(creatorName=...) 失败: {e}")

    def test_username_kwarg_invalid_for_self_contained(self):
        """[BUG-COPY-CONTENT] username= 是错字段, 必须 TypeError 锁住 (防退化)"""
        with pytest.raises(TypeError, match="username"):
            WaitStepContent(wait_time=0, creator=1, username="test")


# ============================================================
# BUG-COPY-CONTENT: 源码层 (copy_content 改造)
# ============================================================

def _mapper_src() -> str:
    from app.mapper.interfaceApi import interfaceCaseContentMapper
    return inspect.getsource(interfaceCaseContentMapper)


def _copy_content_ast() -> ast.FunctionDef:
    """拿到 copy_content 函数的 AST, 用来结构化检查."""
    src = _mapper_src()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "copy_content":
            return node
    raise AssertionError("copy_content not found in mapper src")


def _string_constants_in(node: ast.AST) -> Set[str]:
    """从 AST 节点里收集所有 string literal."""
    return {n.value for n in ast.walk(node)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}




def _mysql_reachable() -> bool:
    """本地 MySQL 可达 = True. 用 2s 超时, 跑默认单测不卡."""
    try:
        import pymysql
        from config import LocalConfig
        conn = pymysql.connect(
            host=LocalConfig.MYSQL_SERVER,
            port=LocalConfig.MYSQL_PORT,
            user="root",
            password=LocalConfig.MYSQL_PASSWORD,
            database=LocalConfig.MYSQL_DATABASE,
            connect_timeout=2,
        )
        conn.close()
        return True
    except Exception:
        return False


class TestBugCopyContentSource:
    """copy_content 源码必须满足: SELF_CONTAINED 分支 + creatorName 字段"""

    def test_copy_content_uses_creator_name_not_username(self):
        """[BUG-COPY-CONTENT] copy_content 必须用 creatorName, 不能再用 username"""
        func = _copy_content_ast()
        strings = _string_constants_in(func)
        assert "creatorName" in strings, (
            f"[{BUG_COPY_CONTENT}] copy_content 必须用 creatorName= 字段, 实际字符串: {strings}"
        )

    def test_copy_content_does_not_pass_username_kwarg(self):
        """[BUG-COPY-CONTENT] copy_content 不能再用 username=user.username 形式"""
        func = _copy_content_ast()
        src = ast.unparse(func)
        # username 只能作为 user.username 右侧的访问属性, 不能再作为 kwarg
        assert "username=" not in src.replace(" ", ""), (
            f"[{BUG_COPY_CONTENT}] copy_content 不能有 username= kwarg:\n{src}"
        )

    def test_copy_content_has_self_contained_branch(self):
        """[BUG-COPY-CONTENT] copy_content 必须有 SELF_CONTAINED_TYPES 分支"""
        func = _copy_content_ast()
        src = ast.unparse(func)
        assert "SELF_CONTAINED" in src, (
            f"[{BUG_COPY_CONTENT}] copy_content 必须有 SELF_CONTAINED_TYPES 分支, 实际:\n{src[:500]}"
        )

    def test_copy_content_uses_introspection_for_child_fields(self):
        """[BUG-COPY-CONTENT] self-contained 分支必须 introspection 复制子表独有列"""
        func = _copy_content_ast()
        src = ast.unparse(func)
        # 必须有 `cls_model.__table__.columns` introspection
        assert "__table__.columns" in src, (
            f"[{BUG_COPY_CONTENT}] self-contained 分支应通过 __table__.columns 反射取子表字段"
        )
        # 必须有 audit 字段过滤 (id/creator 等)
        assert "create_time" in src, (
            f"[{BUG_COPY_CONTENT}] introspection 必须过滤审计字段 (id/uid/create_time/...)"
        )

    def test_copy_content_target_id_branch_preserved(self):
        """[BUG-COPY-CONTENT] 5 种 target_id 类型 (API/GROUP/CONDITION/DB/LOOP) 行为不破坏"""
        func = _copy_content_ast()
        src = ast.unparse(func)
        for case_name in (
            "STEP_API", "STEP_API_GROUP", "STEP_API_CONDITION", "STEP_LOOP",
        ):
            assert case_name in src, (
                f"[{BUG_COPY_CONTENT}] 5 种 target_id 类型的 match case 缺失: {case_name}"
            )

    def test_copy_content_returns_from_self_contained_branch(self):
        """[BUG-COPY-CONTENT] self-contained 分支内必须 add_flush_expunge + return (不走 target_id 后续)"""
        func = _copy_content_ast()
        src = ast.unparse(func)
        # self-contained 块不应有 `new_content.target_id =` 赋值
        # 用 AST 切块: 找 `if ct in SELF_CONTAINED_TYPES` 块
        for node in ast.walk(func):
            if isinstance(node, ast.If):
                test_src = ast.unparse(node.test)
                if "SELF_CONTAINED" in test_src:
                    block_src = ast.unparse(node)
                    assert "new_content.target_id =" not in block_src, (
                        f"[{BUG_COPY_CONTENT}] self-contained 分支不能有 target_id 赋值:\n{block_src}"
                    )
                    assert "add_flush_expunge" in block_src, (
                        f"[{BUG_COPY_CONTENT}] self-contained 分支必须有 add_flush_expunge 写库"
                    )
                    assert "return" in block_src, (
                        f"[{BUG_COPY_CONTENT}] self-contained 分支必须 return 提前结束"
                    )
                    return
        pytest.fail(f"[{BUG_COPY_CONTENT}] copy_content 找不到 if ct in SELF_CONTAINED_TYPES 分支")


# ============================================================
# BUG-COPY-CONTENT: 端到端 (集成, 需要真 DB)
# ============================================================

@pytest.mark.integration
class TestBugCopyContentE2E:
    """集成测试: copy_content 实际能复制 WaitStepContent 不爆

    改用 sync pymysql, 避免 pytest-asyncio 多 loop 切换时 async_session
    scoped session 拿旧 loop 连接导致 RuntimeError (跟 STEP_CACHE E2E
    test_explain_no_filesort 同模式). 集成层, 默认跑跳过.
    """

    def test_copy_wait_step_content_does_not_raise_attribute_error(self):
        """[BUG-COPY-CONTENT] copy_content(WaitStepContent) 不再 AttributeError"""
        if not _mysql_reachable():
            pytest.skip(f"[{BUG_COPY_CONTENT}] 本地 MySQL 不可达, 跳过集成测试")

        import pymysql
        from config import LocalConfig
        conn = pymysql.connect(
            host=LocalConfig.MYSQL_SERVER,
            port=LocalConfig.MYSQL_PORT,
            user="root",
            password=LocalConfig.MYSQL_PASSWORD,
            database=LocalConfig.MYSQL_DATABASE,
            connect_timeout=2,
        )
        try:
            with conn.cursor() as cur:
                # 找一个 wait step + 关联 case
                cur.execute("""
                    SELECT a.interface_case_id, w.step_content_id
                    FROM interface_case_step_wait w
                    JOIN interface_case_content_association a
                      ON a.interface_case_content_id = w.step_content_id
                    LIMIT 1
                """)
                row = cur.fetchone()
                if not row:
                    pytest.skip(f"[{BUG_COPY_CONTENT}] DB 没 (wait step + association), 跳过")
                case_id, content_id = row

                # 记录初始 wait step 数量
                cur.execute("SELECT COUNT(*) FROM interface_case_step_wait")
                cnt_before = cur.fetchone()[0]
        finally:
            conn.close()

        # 调 copy_step (走 InterfaceCaseMapper.copy_step 走完整链路)
        import asyncio
        from app.mapper.interfaceApi.interfaceCaseMapper import InterfaceCaseMapper
        from app.model.base import User

        async def _run():
            fake_user = User(id=1, username="e2e_test")
            await InterfaceCaseMapper.copy_step(
                case_id=case_id, content_id=content_id, user=fake_user,
            )

        try:
            asyncio.run(_run())
        except AttributeError as e:
            pytest.fail(f"[{BUG_COPY_CONTENT}] copy_step 仍 AttributeError: {e}")

        # 验证 wait step 数量 +1
        conn = pymysql.connect(
            host=LocalConfig.MYSQL_SERVER,
            port=LocalConfig.MYSQL_PORT,
            user="root",
            password=LocalConfig.MYSQL_PASSWORD,
            database=LocalConfig.MYSQL_DATABASE,
        )
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM interface_case_step_wait")
                cnt_after = cur.fetchone()[0]
        finally:
            conn.close()

        assert cnt_after == cnt_before + 1, (
            f"[{BUG_COPY_CONTENT}] wait step 数量期望 +1, "
            f"实际 {cnt_before} → {cnt_after}"
        )
