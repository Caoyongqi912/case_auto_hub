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




async def get_subtree_ids(session: AsyncSession, moduleId: int,module_type:int):
    """
    递归查询某个 Module 节点及其所有子节点的 ID。

    :param session: 异步数据库会话
    :param moduleId: 起始节点的 ID
    :param module_type: 起始节点的 ID
    :return: 所有子节点的 ID 列表
    """
    try:
        # 基础查询：选择起始节点
        base_query = select(Module.id).where(and_(
            Module.id == moduleId,
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
    async def query_tree_by(cls, project_id: int, module_type: int):
        """
        查询模块树
        :param project_id:
        :param module_type:
        :return:
        """
        try:
            query_modules: List[Module] = await cls.query_by(project_id=project_id, module_type=module_type)
            if not query_modules:
                return []
            else:
                return await list2Tree(query_modules)
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