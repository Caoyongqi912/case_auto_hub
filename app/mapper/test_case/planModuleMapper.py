#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/25
# @Author : cyq
# @File : planModuleMapper
# @Software: PyCharm
# @Desc: 计划分组数据访问层
from typing import List, Optional

from sqlalchemy import select, delete, and_, func

from app.mapper import Mapper
from app.model.base import User
from app.model.caseHub.plan_module import PlanModule
from app.model.caseHub.association import PlanCaseAssociation
from sqlalchemy.ext.asyncio import AsyncSession
from utils import log


class PlanModuleMapper(Mapper[PlanModule]):
    __model__ = PlanModule
    
    
    @classmethod
    async def init_module(cls,session:AsyncSession,plan_id:int,user:User) -> PlanModule:
        """
        初始化计划分组
        :param session: 会话对象
        :param plan_id: 计划ID
        :param user: 创建人
        :return: 创建的分组
        """
        try:
            module = PlanModule(
                plan_id=plan_id,
                title="全部用例",
                parent_id=None,
                order=0
            )
            module.creator = user.id
            module.creatorName = user.username
            await cls.add_flush_expunge(model=module, session=session)
            return module
        except Exception as e:
            log.error(f"init_module error: {e}")
            raise

    @classmethod
    async def add_module(
        cls,
        plan_id: int,
        title: str,
        user: User,
        parent_id: Optional[int] = None,
        order: int = 0
    ) -> PlanModule:
        """
        添加计划分组
        :param plan_id: 计划ID
        :param title: 分组名称
        :param user: 创建人
        :param parent_id: 父级分组ID
        :param order: 排序顺序
        :return: 创建的分组
        """
        return await cls.save(
            creator_user=user,
            plan_id=plan_id,
            title=title,
            parent_id=parent_id,
            order=order
        )

    @classmethod
    async def update_module(
        cls,
        module_id: int,
        user: User,
        title: Optional[str] = None,
        parent_id: Optional[int] = None,
        order: Optional[int] = None
    ) -> PlanModule:
        """
        更新计划分组
        :param module_id: 分组ID
        :param user: 更新人
        :param title: 分组名称
        :param parent_id: 父级分组ID
        :param order: 排序顺序
        :return: 更新后的分组
        """
        kwargs = {"id": module_id}
        if title is not None:
            kwargs["title"] = title
        if parent_id is not None:
            kwargs["parent_id"] = parent_id
        if order is not None:
            kwargs["order"] = order
        
        return await cls.update_by_id(update_user=user, **kwargs)

    @classmethod
    async def remove_module(cls, module_id: int) -> int:
        """
        删除计划分组（会级联删除子分组）
        :param module_id: 分组ID
        :return: 删除数量
        """
        try:
            async with cls.transaction() as session:
                deleted_count = 0
                
                async def delete_tree(parent_id: int):
                    nonlocal deleted_count
                    stmt = select(PlanModule).where(PlanModule.parent_id == parent_id)
                    result = await session.execute(stmt)
                    children = result.scalars().all()
                    
                    for child in children:
                        await delete_tree(child.id)
                    
                    del_stmt = delete(PlanModule).where(PlanModule.id == parent_id)
                    result = await session.execute(del_stmt)
                    deleted_count += result.rowcount
                
                await delete_tree(module_id)
                return deleted_count
        except Exception as e:
            raise

    @classmethod
    async def move_module(
        cls,
        module_id: int,
        new_parent_id: Optional[int] = None,
        order: Optional[int] = None
    ) -> PlanModule:
        """
        移动计划分组到新的父级分组下
        :param module_id: 分组ID
        :param new_parent_id: 新的父级分组ID，None表示移到根级
        :param order: 排序顺序
        :return: 移动后的分组
        """
        try:
            async with cls.transaction() as session:
                module = await cls.get_by_id(ident=module_id, session=session)
                if not module:
                    raise ValueError("分组不存在")
                
                if new_parent_id is not None:
                    parent = await cls.get_by_id(ident=new_parent_id, session=session)
                    if not parent:
                        raise ValueError("父级分组不存在")
                    if parent.plan_id != module.plan_id:
                        raise ValueError("不能移动到其他计划的分组下")
                
                if new_parent_id is not None:
                    module.parent_id = new_parent_id
                if order is not None:
                    module.order = order
                
                await session.flush()
                return module
        except Exception as e:
            raise

    @classmethod
    async def get_module_tree(cls, plan_id: int) -> List[dict]:
        """
        获取计划下所有分组（树形结构）
        :param plan_id: 计划ID
        :return: 树形结构列表
        """
        try:
            async with cls.transaction() as session:
                stmt = select(PlanModule).where(
                    PlanModule.plan_id == plan_id
                ).order_by(PlanModule.order, PlanModule.create_time)
                result = await session.execute(stmt)
                modules = result.scalars().all()
                return [m.map for m in modules]
        except Exception as e:
            raise

    @classmethod
    async def build_tree(cls, plan_id: int) -> List[dict]:
        """
        构建计划分组的完整树形结构
        :param plan_id: 计划ID
        :return: 树形结构
        """
        try:
            async with cls.transaction() as session:
                count_subq = (
                    select(
                        PlanCaseAssociation.plan_module_id,
                        func.count(PlanCaseAssociation.case_id).label("case_nums")
                    )
                    .where(PlanCaseAssociation.plan_id == plan_id)
                    .group_by(PlanCaseAssociation.plan_module_id)
                    .subquery()
                )
                
                total_count_subq = (
                    select(func.count(PlanCaseAssociation.case_id))
                    .where(PlanCaseAssociation.plan_id == plan_id)
                    .scalar_subquery()
                )
                
                stmt = (
                    select(
                        PlanModule,
                        func.coalesce(count_subq.c.case_nums, 0).label("case_nums"),
                        total_count_subq.label("total_case_nums")
                    )
                    .outerjoin(count_subq, PlanModule.id == count_subq.c.plan_module_id)
                    .where(PlanModule.plan_id == plan_id)
                    .order_by(PlanModule.order, PlanModule.create_time)
                )
                result = await session.execute(stmt)
                rows = result.all()
                
                module_dict = {}
                for row in rows:
                    module_map = row.PlanModule.map.copy()
                    if module_map.get("parent_id") is None:
                        module_map["case_nums"] = row.total_case_nums
                    else:
                        module_map["case_nums"] = row.case_nums
                    module_map["children"] = []
                    module_dict[module_map["id"]] = module_map
                
                root_modules = []
                for module in module_dict.values():
                    parent_id = module.get("parent_id")
                    if parent_id is None:
                        root_modules.append(module)
                    elif parent_id in module_dict:
                        module_dict[parent_id]["children"].append(module)
                
                return root_modules
        except Exception as e:
            log.error(f"build_tree error: {e}")
            raise

    @classmethod
    async def find_or_create_path(
        cls,
        plan_id: int,
        title_path: List[str],
        user: User,
    ) -> "PlanModule":
        """
        按 title_path 列表在指定 plan 的 ROOT 目录下逐级 find-or-create, 返回叶子 PlanModule.

        重要约定: Excel 上传的目录必须挂在 plan 的根目录 (parent_id=NULL, 由 plan 创建时
        init_module 自动生成, title="全部用例") 之下, 不能与 root 同级. 原因:
        - 根目录用于收口"全量用例"语义, 是 UI 树默认展开的锚点
        - 同级散落会破坏树的单一入口, 让 "全量统计" 失去意义

        查找维度: (plan_id, parent_id, title)
        - 第一级以 root.id 作为 parent_id
        - 后续级别以递归创建的节点 id 作为 parent_id
        静默复用现有匹配项; 若不存在则新建.
        父级不存在时一并创建.

        :param plan_id: 计划 ID
        :param title_path: 标题路径列表, 例 ["登录","表单"]; 空列表抛 ValueError
        :param user: 创建人 (新建节点时记录创建人)
        :return: 叶子 PlanModule 实例
        :raises ValueError: title_path 为空 / 包含空标题 / plan 缺少根目录
        """
        if not title_path:
            raise ValueError("title_path 不能为空")
        cleaned = [(t or "").strip() for t in title_path]
        if any(not t for t in cleaned):
            raise ValueError("title_path 中存在空标题段")

        async with cls.transaction() as session:
            # 1) 找到 plan 的根目录 (parent_id=NULL).
            #    init_module 会在 plan 创建时建好; 若缺失说明数据异常, 抛错让上层感知.
            #    用 order, id 排序兜底多根的极端情况, 取最靠前那一个.
            root_stmt = (
                select(PlanModule)
                .where(
                    PlanModule.plan_id == plan_id,
                    PlanModule.parent_id.is_(None),
                )
                .order_by(PlanModule.order, PlanModule.id)
            )
            root_module = (await session.execute(root_stmt)).scalars().first()
            if root_module is None:
                raise ValueError(
                    f"plan_id={plan_id} 缺少根目录, 请先初始化"
                )

            # 2) 计算同一 plan 内最大 order, 新建节点接在末尾 (避免插入到中间)
            async def _next_order(s: AsyncSession) -> int:
                stmt = select(func.coalesce(func.max(PlanModule.order), 0)).where(
                    PlanModule.plan_id == plan_id
                )
                return (await s.execute(stmt)).scalar() + 1

            # 3) 以 root 作为第一级 parent, 逐级 find-or-create
            parent_id: Optional[int] = root_module.id
            leaf: Optional[PlanModule] = None
            for title in cleaned:
                stmt = select(PlanModule).where(
                    PlanModule.plan_id == plan_id,
                    PlanModule.parent_id == parent_id,
                    PlanModule.title == title,
                )
                existing = (await session.execute(stmt)).scalars().first()
                if existing:
                    leaf = existing
                else:
                    leaf = await cls.save(
                        creator_user=user, session=session,
                        plan_id=plan_id,
                        parent_id=parent_id,
                        title=title,
                        order=await _next_order(session),
                    )
                parent_id = leaf.id
            return leaf
