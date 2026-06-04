from typing import List

from sqlalchemy import delete, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper
from app.model import async_session
from app.model.base.module import Module
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
        查询模块树，包含未分组数据汇总
        :param project_id:
        :param module_type:
        :return:
        """
        try:
            query_modules: List[Module] = await cls.query_by(project_id=project_id, module_type=module_type)
            if not query_modules:
                return []

            tree = await list2Tree(query_modules)
            if no_group:
                return tree
            
            ungrouped_modules = [m for m in query_modules if m.parent_id is None and m.title != "未分组"]
            if ungrouped_modules:
                ungrouped_node = {
                    "key": f"ungrouped_module_{module_type}",
                    "title": "未分组数据",
                    "parent_id": None,
                    "project_id": project_id,
                    "module_type": module_type
                }
                tree.append(ungrouped_node)

            return tree
        except Exception as e:
            log.error(e)
            return []


    @classmethod
    async def remove_module(cls, moduleId: int):
        try:
            async with async_session() as session:
                async with session.begin():
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
            async with async_session() as session:
                module: Module = await cls.get_by_id(id, session)
                if targetId:
                    target_module: Module = await cls.get_by_id(targetId, session)
                    module.parent_id = target_module.id
                else:
                    module.parent_id = None
                session.add(module)
                await session.commit()
        except Exception as e:
            raise e