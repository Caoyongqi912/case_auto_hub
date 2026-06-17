from typing import Dict, List, Optional

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper
from app.model.base.module import Module
from enums import ModuleEnum
from utils import log


async def list2Tree(datas: List[Module]):
    """
    列表转树
    :param datas:
    :return:
    """
    data = [data.map for data in datas]
    mapping ={item['key']: item for item in data}
    tree = []
    for item in data:
        parent_key = item.get('parent_id')
        parent = mapping.get(parent_key) if parent_key else None

        if parent is None:
            tree.append(item)
        else:
            children = parent.setdefault("children", [])
            children.append(item)
            parent["children_length"] = len(children)
    return tree




async def get_subtree_ids(session: AsyncSession, module_id: int,module_type:int):
    """
    递归查询某个 Module 节点及其所有子节点的 ID。

    :param session: 异步数据库会话
    :param module_id: 起始节点的 ID
    :param module_type: 模块类型
    :return: 所有子节点的 ID 列表
    """
    try:
        # 基础查询：选择起始节点
        base_query = select(Module.id).where(and_(
            Module.id == module_id,
            Module.module_type == module_type
        ))
        # 递归 CTE：查询所有子节点
        cte = base_query.cte(name='ChildRecords', recursive=True)
        cte = cte.union_all(
            select(Module.id)
            .where(Module.parent_id == cte.c.id)
        )
        # 最终查询：选择所有子节点的 ID
        recursive_query = select(cte.c.id)
        return (await session.execute(recursive_query)).scalars().all()
    except Exception as e:
        log.error(f"递归查询失败: {e}")
        raise e


class ModuleMapper(Mapper[Module]):
    __model__ = Module

    @classmethod
    async def query_tree_by(cls, project_id: int, module_type: int, no_group: bool = False):
        """
        查询模块树，包含未分组数据汇总。

        用例库 (module_type=CASE) 会为每个模块挂上 `count` 字段:
        父目录的 count = 自身直接关联的用例数 + 全部后代模块的用例数之和。
        其它 module_type 暂不统计, count 默认为 0 (前端 `count>0` 才显示徽标)。

        :param project_id: 项目 ID
        :param module_type: 模块类型 (ModuleEnum)
        :param no_group: True 时不附加 "未分组数据" 虚拟节点
        :return: 嵌套的模块树, 每个节点可能携带 `count` 字段
        """
        try:
            query_modules: List[Module] = await cls.query_by(project_id=project_id, module_type=module_type)
            if not query_modules:
                return []

            tree = await list2Tree(query_modules)

            # 用例库才统计 count; 其它 module_type 暂未实现, 直接跳过统计步骤
            # (count 保持缺省, 不会在前端渲染徽标)
            case_counts: Dict[int, int] = {}
            ungrouped_count: int = 0
            if module_type == ModuleEnum.CASE:
                from app.model.caseHub.test_case import TestCase
                async with cls.session_scope() as session:
                    # 每个 module_id 直接关联的用例数 (is_common=True 即 "用例库")
                    direct_count_stmt = (
                        select(TestCase.module_id, func.count(TestCase.id))
                        .where(
                            TestCase.project_id == project_id,
                            TestCase.is_common.is_(True),
                            TestCase.module_id.is_not(None),
                        )
                        .group_by(TestCase.module_id)
                    )
                    rows = (await session.execute(direct_count_stmt)).all()
                    case_counts = {int(mid): int(cnt) for mid, cnt in rows if mid is not None}

                    # 未分组 (module_id IS NULL) 的用例数
                    ungrouped_stmt = (
                        select(func.count(TestCase.id))
                        .where(
                            TestCase.project_id == project_id,
                            TestCase.is_common.is_(True),
                            TestCase.module_id.is_(None),
                        )
                    )
                    ungrouped_count = int((await session.execute(ungrouped_stmt)).scalar() or 0)

            # 第一步: 把每个节点的 count 初始化为自身直接关联的用例数
            def _init_counts(node: dict) -> None:
                node["count"] = int(case_counts.get(node["key"], 0))
                for child in node.get("children") or []:
                    _init_counts(child)

            for root in tree:
                _init_counts(root)

            # 第二步: 后序遍历把后代 count 累加到父节点
            # 父.count = 父.count + Σ child.count
            def _aggregate(node: dict) -> int:
                total = int(node.get("count", 0))
                for child in node.get("children") or []:
                    total += _aggregate(child)
                node["count"] = total
                return total

            for root in tree:
                _aggregate(root)

            if no_group:
                return tree

            ungrouped_modules = [m for m in query_modules if m.parent_id is None and m.title != "未分组"]
            if ungrouped_modules:
                ungrouped_node = {
                    "key": f"ungrouped_module_{module_type}",
                    "title": "未分组数据",
                    "parent_id": None,
                    "project_id": project_id,
                    "module_type": module_type,
                    "count": ungrouped_count,
                }
                tree.append(ungrouped_node)

            return tree
        except Exception as e:
            log.error(e)
            return []


    @classmethod
    async def remove_module(cls, moduleId: int):
        try:
            async with cls.transaction() as session:
                module:Module = await cls.get_by_id(moduleId, session)
                if module.parent_id is None:
                    subId = await get_subtree_ids(session, moduleId,module.module_type)
                    if subId:
                        for i in subId:
                            await session.execute(delete(Module).where(Module.id == i))
                await session.delete(module)
        except Exception as e:
            raise e




    @classmethod
    async def find_path(
        cls,
        project_id: int,
        title_path: List[str],
        module_type: int,
    ) -> Optional[int]:
        """
        按 title_path 列表逐级查找, 返回叶子 Module.id; 任一级不存在返回 None.

        与 find_or_create_path 的区别:
        - 本方法**只查不建**, 缺失即返回 None (无副作用)
        - 用于"系统必须先有这个目录才允许导入"这类硬门禁校验:
          校验失败由调用方决定是整批拒绝还是跳过坏行
        - 走读事务 (expire 无关, 只读不写)

        :param project_id: 项目 ID
        :param title_path: 标题路径列表, 例 ["二手","交易"]; 空列表返回 None
        :param module_type: 模块类型 (ModuleEnum.CASE / API ...)
        :return: 叶子 Module.id; 任一级缺失返回 None
        """
        if not title_path:
            return None
        cleaned = [(t or "").strip() for t in title_path]
        if any(not t for t in cleaned):
            return None

        async with cls.session_scope() as session:
            parent_id: Optional[int] = None
            for title in cleaned:
                if parent_id is None:
                    cond = Module.parent_id.is_(None)
                else:
                    cond = Module.parent_id == parent_id
                stmt = select(Module).where(
                    Module.project_id == project_id,
                    Module.module_type == module_type,
                    cond,
                    Module.title == title,
                )
                node = (await session.execute(stmt)).scalars().first()
                if node is None:
                    return None
                parent_id = node.id
            return parent_id

    @classmethod
    async def find_or_create_path(
        cls,
        project_id: int,
        title_path: List[str],
        module_type: int,
        user: "User",
    ) -> Module:
        """
        按 title_path 列表逐级 find-or-create, 返回叶子 Module.

        查找维度: (project_id, module_type, parent_id, title)
        静默复用现有匹配项; 若不存在则新建.
        并发安全: 依赖表上的 uq_module_path 唯一约束, IntegrityError 时重查一次.

        :param project_id: 项目 ID
        :param title_path: 标题路径列表, 例 ["二手","交易","待办流程","PC"]; 空列表抛 ValueError
        :param module_type: 模块类型 (ModuleEnum.CASE / API ...)
        :param user: 创建人
        :return: 叶子 Module 实例
        """
        if not title_path:
            raise ValueError("title_path 不能为空")
        cleaned = [(t or "").strip() for t in title_path]
        if any(not t for t in cleaned):
            raise ValueError("title_path 中存在空标题段")

        from sqlalchemy.exc import IntegrityError
        from app.model.base import User

        async with cls.transaction() as session:
            parent_id: Optional[int] = None
            leaf: Optional[Module] = None
            for title in cleaned:
                if parent_id is None:
                    cond = Module.parent_id.is_(None)
                else:
                    cond = Module.parent_id == parent_id
                stmt = select(Module).where(
                    Module.project_id == project_id,
                    Module.module_type == module_type,
                    cond,
                    Module.title == title,
                )
                existing = (await session.execute(stmt)).scalars().first()
                if existing:
                    leaf = existing
                else:
                    try:
                        leaf = await cls.save(
                            creator_user=user, session=session,
                            project_id=project_id,
                            parent_id=parent_id,
                            title=title,
                            module_type=module_type,
                        )
                    except IntegrityError:
                        # 并发场景: 别人刚创建了同路径节点, 重查一次
                        await session.rollback()
                        leaf = (await session.execute(stmt)).scalars().first()
                        if not leaf:
                            raise
                parent_id = leaf.id
            return leaf

    @classmethod
    async def drop(cls, id: int, targetId: int | None):
        try:
            async with cls.transaction() as session:
                module: Module = await cls.get_by_id(id, session)
                if targetId:
                    target_module: Module = await cls.get_by_id(targetId, session)
                    module.parent_id = target_module.id
                else:
                    module.parent_id = None
                session.add(module)
        except Exception as e:
            raise e