"""
2026-06-22 Round 2 detached instance

触发: 端点 GET /interfaceCase/content/query_contents?case_id=7
 报 "Parent instance <GroupStepContent ...> is not bound to a Session;
 lazy load operation of attribute 'interface_group' cannot proceed"

回归: tests/croe/interface/test_bug_group_detached_fix.py

覆盖:
- 新方法 query_content_dicts 存在
- query_content_dicts 走 selectinload(GroupStepContent.interface_group)
- query_content_dicts 走 selectinload(DBStepContent.db_execute)
- query_content_dicts 在 session 内 to_dict() 返 dict 列表 (不是 ORM 对象)
- query_steps 不被改 (D5 决策保留)
- query_contents controller 改调 query_content_dicts
"""
import ast
import inspect
import re

import pytest

from app.mapper.interfaceApi import interfaceCaseMapper
from app.mapper.interfaceApi.interfaceCaseMapper import InterfaceCaseMapper
from tests.croe.interface._bug_ids import BUG_GROUP_DETACHED


def _query_content_dicts_src() -> str:
    return inspect.getsource(InterfaceCaseMapper.query_content_dicts)


def _query_contents_controller_src() -> str:
    from app.controller.interface import interfaceCaseController
    return inspect.getsource(interfaceCaseController)


# ============================================================
# 新方法存在 + 用 selectinload 预加载
# ============================================================
class TestBugGroupDetachedNewMethod:
    """query_content_dicts 必须存在并选inload 两个 lazy='select' 的 relationship"""

    def test_query_content_dicts_method_exists(self):
        """InterfaceCaseMapper.query_content_dicts 必须存在"""
        assert hasattr(InterfaceCaseMapper, "query_content_dicts"), (
            f"[{BUG_GROUP_DETACHED}] InterfaceCaseMapper 缺 query_content_dicts 方法"
        )
        assert inspect.iscoroutinefunction(InterfaceCaseMapper.query_content_dicts), (
            f"[{BUG_GROUP_DETACHED}] query_content_dicts 必须是 async 函数"
        )

    def test_query_content_dicts_has_group_selectinload(self):
        """selectinload(GroupStepContent.interface_group) 必须有"""
        src = _query_content_dicts_src()
        assert "selectinload(GroupStepContent.interface_group)" in src, (
            f"[{BUG_GROUP_DETACHED}] query_content_dicts 必须 selectinload "
            f"GroupStepContent.interface_group, 否则 to_dict() 访问 .interface_group "
            f"走 lazy='select' 爆 detached"
        )

    def test_query_content_dicts_has_db_selectinload(self):
        """selectinload(DBStepContent.db_execute) 必须有 (同样问题)"""
        src = _query_content_dicts_src()
        assert "selectinload(DBStepContent.db_execute)" in src, (
            f"[{BUG_GROUP_DETACHED}] query_content_dicts 必须 selectinload "
            f"DBStepContent.db_execute, 同样 lazy='select' 问题, 一起修"
        )

    def test_query_content_dicts_returns_list_not_sequence(self):
        """返回类型注解应是 List[Dict] (不是 Sequence[Any])"""
        sig = inspect.signature(InterfaceCaseMapper.query_content_dicts)
        ret = sig.return_annotation
        ret_str = ast.unparse(ast.parse(str(ret), mode="eval").body) if ret is not inspect.Signature.empty else ""
        assert "List" in ret_str, (
            f"[{BUG_GROUP_DETACHED}] query_content_dicts 返回类型应为 List, 实际: {ret_str}"
        )

    def test_query_content_dicts_to_dict_inside_session(self):
        """to_dict 必须在 session_scope 块内执行"""
        src = _query_content_dicts_src()
        m = re.search(
            r"async with cls\.session_scope\(session\) as s:\s*\n"
            r"((?:[ \t]+[^\n]*\n)+)",
            src,
        )
        assert m, "query_content_dicts 必须有 async with cls.session_scope 块"
        block = m.group(1)
        assert "to_dict" in block, (
            f"[{BUG_GROUP_DETACHED}] to_dict() 必须在 session_scope 块内执行, "
            f"否则关闭 session 后再 to_dict 还会爆 detached"
        )

    def test_query_content_dicts_returns_to_dict_results(self):
        """返回语句应是 list comprehension of to_dict()"""
        src = _query_content_dicts_src()
        assert re.search(r"return\s+\[\s*step\.to_dict\(\)\s+for\s+step\s+in\s+steps\s*\]", src), (
            f"[{BUG_GROUP_DETACHED}] query_content_dicts 应 return "
            f"[step.to_dict() for step in steps] 立即序列化"
        )

    def test_query_content_dicts_uses_options_clause(self):
        """selectinload 必须放在 .options() 子句里"""
        src = _query_content_dicts_src()
        m = re.search(r"\.options\(\s*(.+?)\s*\)", src, re.DOTALL)
        assert m, (
            f"[{BUG_GROUP_DETACHED}] query_content_dicts 必须有 .options(selectinload(...))"
        )
        options_body = m.group(1)
        assert "selectinload" in options_body, (
            f"[{BUG_GROUP_DETACHED}] .options() 块内必须有 selectinload"
        )


# ============================================================
# controller 调新方法
# ============================================================
class TestBugGroupDetachedController:
    """query_contents controller 必须改调 query_content_dicts"""

    def _extract_query_contents(self, src: str) -> str:
        """从 controller 源码里抽取 query_contents 函数体"""
        start = src.find("async def query_contents")
        assert start >= 0, "query_contents 函数未找到"
 # 找下一个顶层 def / class / decorator
        end = len(src)
        for m in re.finditer(r"\n(class |@router|@app\.|def |async def )", src[start+1:]):
            end = start + 1 + m.start()
            break
        return src[start:end]

    def test_controller_calls_query_content_dicts(self):
        """query_contents controller 必须调 query_content_dicts"""
        src = _query_contents_controller_src()
        body = self._extract_query_contents(src)
        assert "query_content_dicts" in body, (
            f"[{BUG_GROUP_DETACHED}] query_contents controller 必须调 query_content_dicts"
        )
        assert "query_steps(case_id=case_id)" not in body, (
            f"[{BUG_GROUP_DETACHED}] query_contents controller 不应再调 "
            f"query_steps(case_id=case_id) (会爆 detached)"
        )

    def test_controller_does_not_just_query_steps(self):
        """query_contents 内只调 query_content_dicts (不能是 query_steps 的某种别名)"""
        src = _query_contents_controller_src()
        body = self._extract_query_contents(src)
        body_no_comments = "\n".join(l for l in body.split("\n") if not l.strip().startswith("#"))
        assert "query_content_dicts" in body_no_comments, (
            f"[{BUG_GROUP_DETACHED}] query_contents 实际代码缺 query_content_dicts 调用"
        )


# ============================================================
# query_steps 不被破坏 (D5 决策保留)
# ============================================================
class TestBugGroupDetachedQueryStepsUnchanged:
    """query_steps 仍走 D5 修后的形态, 不被本批改动污染"""

    def test_query_steps_no_options_clause(self):
        """query_steps 仍不应有 .options() (D5 不重叠)"""
        src = inspect.getsource(InterfaceCaseMapper.query_steps)
        code_lines = [l for l in src.split("\n") if not l.strip().startswith("#")]
        code = "\n".join(code_lines)
        assert ".options(" not in code, (
            f"[{BUG_GROUP_DETACHED}] query_steps 不应有 .options() (D5 决策保留, "
            f"本批不动 query_steps, 加 selectinload 会让 5 个 step strategy 路径浪费)"
        )

    def test_query_steps_no_joinedload(self):
        """query_steps 仍不应有 joinedload (D5, 实际代码, 排除注释)"""
        src = inspect.getsource(InterfaceCaseMapper.query_steps)
 # 排除 # 注释行 (D5 修注释里提了 5 个 joinedload, 不能误命中)
        code_lines = [l for l in src.split("\n") if not l.strip().startswith("#")]
        code = "\n".join(code_lines)
        assert "joinedload" not in code, (
            f"[{BUG_GROUP_DETACHED}] query_steps 实际代码不应有 joinedload (D5 删 5 个死 joinedload)"
        )

    def test_query_steps_returns_sequence(self):
        """query_steps 仍返 Sequence (ORM 对象, 给 step strategy)"""
        sig = inspect.signature(InterfaceCaseMapper.query_steps)
        ret = sig.return_annotation
        ret_str = ast.unparse(ast.parse(str(ret), mode="eval").body) if ret is not inspect.Signature.empty else ""
        assert "Sequence" in ret_str, (
            f"[{BUG_GROUP_DETACHED}] query_steps 返回类型应是 Sequence (ORM 对象), 实际: {ret_str}"
        )


# ============================================================
# mapper 文件 import 验证
# ============================================================
class TestBugGroupDetachedImports:
    """interfaceCaseMapper 必须 import selectinload"""

    def test_mapper_imports_selectinload(self):
        """interfaceCaseMapper 必须 import selectinload"""
        src = inspect.getsource(interfaceCaseMapper)
        assert "from sqlalchemy.orm import selectinload" in src, (
            f"[{BUG_GROUP_DETACHED}] interfaceCaseMapper 必须 import selectinload"
        )


# ============================================================
# 端到端校验 - to_dict 后访问 property 不爆
# ============================================================
class TestBugGroupDetachedToDictSafe:
    """模拟 detached: to_dict 后, 访问 dict 字段不应再触发 lazy load"""

    def test_to_dict_result_is_plain_dict(self):
        """query_content_dicts 返回的元素是 dict, 不是 ORM 对象"""
        src = _query_content_dicts_src()
        assert re.search(r"\[.*\.to_dict\(\).*for.*in.*\]", src), (
            f"[{BUG_GROUP_DETACHED}] query_content_dicts 应返 list of dicts"
        )
        sig = inspect.signature(InterfaceCaseMapper.query_content_dicts)
        ret_str = str(sig.return_annotation)
        assert "Sequence" not in ret_str, (
            f"[{BUG_GROUP_DETACHED}] query_content_dicts 不应返 Sequence (那是 query_steps 的语义)"
        )

    def test_group_step_content_property_chain(self):
        """GroupStepContent.to_dict 链路: content_desc -> interface_group

 静态锁: GroupStepContent 的 interface_num / content_desc property
 都访问 self.interface_group, 这些 property 在 to_dict 路径里必触发,
 所以 selectinload 必须存在。
 """
        from app.model.interfaceAPIModel.contents.groupStepContentModel import GroupStepContent
        props = []
        for name in dir(GroupStepContent):
            if name.startswith("_"):
                continue
            attr = getattr(GroupStepContent, name, None)
            if isinstance(attr, property):
                props.append(name)
        for prop_name in ("content_desc", "interface_num"):
            assert prop_name in props, (
                f"[{BUG_GROUP_DETACHED}] GroupStepContent.{prop_name} 应是 property"
            )
        src = inspect.getsource(GroupStepContent)
        for prop_name in ("content_desc", "interface_num"):
            m = re.search(rf"(?:@property\s*\n)?def\s+{prop_name}\(self.*?(?=\n    @|\n    def |\nclass |\Z)",
                          src, re.DOTALL)
            assert m, f"GroupStepContent.{prop_name} 未找到"
            body = m.group(0)
            assert "self.interface_group" in body, (
                f"[{BUG_GROUP_DETACHED}] GroupStepContent.{prop_name} 实际代码未访问 "
                f"self.interface_group, 链路断了, 测试需要更新"
            )

    def test_db_step_content_property_chain(self):
        """DBStepContent.content_desc 访问 self.db_execute (同样问题)"""
        from app.model.interfaceAPIModel.contents.dbStepContentModel import DBStepContent
        src = inspect.getsource(DBStepContent)
        m = re.search(
            r"(?:@property\s*\n)?def\s+content_desc\(self.*?(?=\n    @|\n    def |\nclass |\Z)",
            src, re.DOTALL,
        )
        assert m, "DBStepContent.content_desc 未找到"
        body = m.group(0)
        assert "self.db_execute" in body, (
            f"[{BUG_GROUP_DETACHED}] DBStepContent.content_desc 应访问 self.db_execute"
        )
