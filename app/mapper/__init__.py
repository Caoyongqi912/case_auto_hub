#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/6/6
# @Author : cyq
# @File : __init__.py
# @Software: PyCharm
# @Desc: Mapper基础类，提供通用的数据库操作方法
import json
from contextlib import asynccontextmanager
from math import ceil
from typing import TypeVar, List, Type, Any, Optional, Generic, Dict, Union, Sequence, AsyncIterator, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text, delete, update

from app.exception import NotFind, CommonError
from app.model import async_session, BaseModel
from app.model.base import User
from utils import log


def calc_total_pages(total: int, page_size: int) -> int:
    """计算总页数"""
    if total is None or total == 0:
        return 0
    return ceil(total / page_size)


def set_creator(user: User, **kwargs):
    """设置创建人信息"""
    kwargs.update({"creator": user.id, "creatorName": user.username})
    return kwargs


def set_updater(user: User, **kwargs):
    """设置更新人信息"""
    kwargs.update({"updater": user.id, "updaterName": user.username})
    return kwargs


M = TypeVar('M', bound=BaseModel)


class Mapper(Generic[M]):
    """通用Mapper基类，提供标准的CRUD操作"""
    __model__: Type[M] | Any

    # def __init_subclass__(cls, **kwargs):
    #     super().__init_subclass__(**kwargs)
    #     if not hasattr(cls, '__model__'):
    #         raise TypeError(f"{cls.__name__} 必须定义 __model__ 类变量")

    @classmethod
    @asynccontextmanager
    async def session_scope(cls, session: AsyncSession = None) -> AsyncGenerator[AsyncSession, None]:
        """
        Session 上下文管理器

        如果传入 session 则直接使用，否则创建新 session

        Args:
            session: 可选的数据库会话

        Yields:
            AsyncSession: 数据库会话
        """
        if session:
            yield session
        else:
            async with async_session() as s:
                yield s


    @classmethod
    async def _execute_query(cls, stmt, session: Optional[AsyncSession] = None):
        """
        执行查询语句，统一通过 session_scope 管理会话生命周期。

        - 传入外部 session：直接在其上执行，不管理生命周期
        - 未传入 session：自动创建临时 session，执行后自动关闭

        Args:
            stmt: SQLAlchemy 查询语句
            session: 可选的外部会话对象

        Returns:
            Result: 查询结果对象
        """
        # 统一委托给 session_scope 处理 session 的传入/创建逻辑
        # 消除原先 if session is None 分支的重复样板代码
        async with cls.session_scope(session) as session:
            return await session.execute(stmt)

    @classmethod
    async def _get_by_field(cls, field_name: str, value: Any, session: Optional[AsyncSession] = None,
                            raise_error: bool = True, desc: str = '') -> M:
        """
        通过字段获取对象的通用方法
        :param field_name: 字段名
        :param value: 字段值
        :param session: 可选的会话对象
        :param raise_error: 是否抛出异常
        :param desc: 错误描述
        :return: 模型实例
        """
        model = cls.__model__
        try:
            field = getattr(model, field_name)
            stmt = select(model).where(field == value)
            result = await cls._execute_query(stmt, session)
            instance = result.scalar_one_or_none()

            if not instance and raise_error:
                error_msg = f"数据{desc}不存在或已经删除，{field_name}: {value}" if desc else f"数据不存在，{field_name}: {value}"
                raise NotFind(error_msg)
            return instance
        except NotFind:
            raise
        except Exception as e:
            log.exception(f"获取{cls.__name__}对象失败，{field_name}: {value}, 错误: {e}")
            raise

    @classmethod
    async def insert(cls, model: M) -> M:
        """模型入库"""
        return await cls._manage_session(session=None, model=model)

    @classmethod
    async def save(cls, creator_user: User = None, session: AsyncSession = None, **kwargs) -> M:
        """
        保存模型实例到数据库，处理创建人信息并返回模型实例
        :param creator_user: 创建人
        :param session: 可选的会话对象
        :param kwargs: 模型字段
        :return: 模型实例
        """
        if creator_user:
            kwargs = set_creator(creator_user, **kwargs)

        try:
            model = cls.__model__(**kwargs)
            return await cls._manage_session(session, model)
        except Exception as e:
            log.exception(f"保存{cls.__name__}失败: {e}")
            raise

    @classmethod
    async def copy_one(cls, target: Union[int,BaseModel], session: AsyncSession, user: User = None, **kwargs) -> M:
        """复制模型实例"""
        if isinstance(target, BaseModel):
            old_one = target
        else:
            old_one = await cls.get_by_id(target, session)
        new_one = cls.__model__(**old_one.copy_map())
        if user:
            new_one.creator = user.id
            new_one.creatorName = user.username
        if kwargs:
            for k, v in kwargs.items():
                if hasattr(new_one, k):
                    setattr(new_one, k, v)
        return await cls.add_flush_expunge(session, new_one)

    @classmethod
    async def get_by_id(cls, ident: int, session: AsyncSession = None, desc: str = '') -> M:
        """
        通过id获取对象
        :param ident: id
        :param session: 可选的会话对象
        :param desc: 错误描述
        :return: 模型实例
        """
        model = cls.__model__
        try:
            async with cls.session_scope(session) as session:
                instance = await session.get(model, ident)
                if not instance:
                    error_msg = f"数据{desc}不存在或已经删除，id: {ident}" if desc else f"数据不存在，id: {ident}"
                    raise NotFind(error_msg)
                return instance
        except NotFind:
            raise
        except Exception as e:
            log.exception(f"获取{cls.__name__}对象失败，id: {ident}, 错误: {e}")
            raise

    @classmethod
    async def get_by_uid(cls, uid: str, session: AsyncSession = None, raise_error: bool = True) -> M:
        """
        通过uid获取对象
        :param uid: uid
        :param session: 可选的会话对象
        :param raise_error: 是否抛出异常
        :return: 模型实例
        """
        return await cls._get_by_field('uid', uid, session, raise_error)

    @classmethod
    async def update_by_id(
        cls,
        session: AsyncSession = None,
        update_user: User = None,
        post_update_hook: Optional[callable] = None,
        **kwargs,
    ) -> M:
        """
        通过 id 更新模型实例。

        事务边界说明：
        - 传入外部 session：在其上执行更新并 flush，由调用方控制 commit
        - 未传入 session：自动创建 session + 事务，更新后自动 commit

        Args:
            session: 可选的外部会话对象
            update_user: 更新人信息（自动注入 updater/updaterName）
            post_update_hook: 在 expunge 之前调用的 callback,
                签名 `async (target) -> Any` 或 `def (target) -> Any`。
                用于在 target 还 attached 时拿 to_dict() 快照, 避免 expunge
                后 lazy='selectin' 关系访问 detached instance 报错。
                返回值会被透传出去。
            **kwargs: 更新字段（必须包含 id）

        Returns:
            M: 更新后的模型实例 (或 post_update_hook 的返回值, 如果提供)

        Raises:
            ValueError: kwargs 中缺少 id 时抛出
        """
        try:
            ident = kwargs.pop("id", None)
            if ident is None:
                raise ValueError("id parameter is required")

            if update_user:
                kwargs = set_updater(update_user, **kwargs)

            # 统一使用 transaction(session) 处理 session 和事务：
            # - session 不为 None：复用它，在其上执行操作并 flush（不擅自 commit）
            # - session 为 None：transaction() 自动创建新 session + begin，退出时自动 commit
            async with cls.transaction(session) as session:
                target = await cls.get_by_id(ident, session)
                await cls.update_cls(target, session, **kwargs)
                # 在 expunge 之前 (target 还 attached) 跑 hook,
                # 防止 lazy='selectin' 关系访问 detached instance
                if post_update_hook is not None:
                    result = post_update_hook(target)
                    if hasattr(result, '__await__'):
                        result = await result
                    return result
                return target
        except Exception as e:
            log.exception(f"error: {e}")
            raise

    @classmethod
    async def update_by_uid(cls, update_user: User = None, **kwargs):
        """
        通过 uid 更新模型实例。

        自动创建 session + 事务，更新后自动 commit。

        Args:
            update_user: 更新人信息（自动注入 updater/updaterName）
            **kwargs: 更新字段（必须包含 uid）

        Returns:
            M: 更新后的模型实例
        """
        kwargs = set_updater(update_user, **kwargs)

        try:
            uid = kwargs.pop("uid")
            # 统一使用 transaction() 管理 session 和事务
            # 替代原先的手动 async_session() + session.begin() 模式
            async with cls.transaction() as session:
                target = await cls.get_by_uid(uid, session)
                return await cls.update_cls(target, session, **kwargs)
        except Exception as e:
            log.exception(f"update_by_uid error: {e}")
            raise

    @classmethod
    async def delete_by_uid(cls, uid: str):
        """
        通过 uid 删除记录。

        使用 transaction() 统一管理事务：
        - 自动创建 session + 事务
        - 执行 delete 后自动 commit
        - 异常时自动 rollback

        Args:
            uid: 待删除记录的唯一标识 uid
        """
        model = cls.__model__
        try:
            # 统一使用 transaction() 管理 session 和事务
            # 替代原先的手动 async_session() + commit 模式
            async with cls.transaction() as session:
                await session.execute(delete(model).where(model.uid == uid))
        except Exception as e:
            log.exception(f"error: {e}")
            raise

    @classmethod
    async def delete_by_id(cls, ident: int, session: AsyncSession = None):
        """
        通过id删除

        事务边界说明：
        - 传入外部 session：仅执行 delete 并 flush，由调用方控制 commit
          （适用于调用方需要在同一事务中执行多个操作的场景）
        - 未传入 session：自动创建 session + 事务，执行 delete 后自动 commit

        Args:
            ident: 待删除记录的主键 ID
            session: 可选的外部会话对象。传入时由调用方管理事务；
                     未传入时由本方法自动管理事务。
        """
        model = cls.__model__
        stmt = delete(model).where(model.id == ident)
        try:
            if session is not None:
                # 复用外部 session：仅执行操作并 flush，不擅自 commit
                # 避免破坏调用方的事务边界（如调用方在 transaction() 中执行多个操作）
                await session.execute(stmt)
                await session.flush()
            else:
                # 自行管理 session + 事务：执行 delete 后自动 commit
                async with cls.transaction() as session:
                    await session.execute(stmt)
        except Exception as e:
            log.exception(f"error: {e}")
            raise

    @classmethod
    async def delete_by(cls, session: AsyncSession=None, **kwargs):
        """
        通过属性删除
        :param session: 会话对象
        :param kwargs: 查询条件
        """
        try:
            async with cls.session_scope(session) as session:
                async with session.begin():
                    model = cls.__model__
                    log.debug(model)
                    await session.execute(delete(model).filter_by(**kwargs))
        except Exception as e:
            log.exception(f"delete_by error: {e}")
            raise

    @classmethod
    async def get_by(cls, session: AsyncSession = None, **kwargs) -> Optional[M]:
        """
        通过字段获取单个对象。

        - 传入外部 session：在其上执行查询
        - 未传入 session：自动创建临时 session，查询后自动关闭

        Args:
            session: 可选的外部会话对象
            **kwargs: 查询条件（filter_by 语义）

        Returns:
            Optional[M]: 匹配的第一个模型实例，不存在则返回 None
        """
        model = cls.__model__
        sql = select(model).filter_by(**kwargs)
        # 统一使用 session_scope 消除 if session 分支
        async with cls.session_scope(session) as session:
            result = await session.scalars(sql)
            return result.first()

    @classmethod
    async def query_all(cls) -> List[M]:
        """
        查询所有数据。

        自动创建临时 session 执行全表查询，完成后自动关闭。

        Returns:
            List[M]: 所有模型实例列表
        """
        model = cls.__model__
        # 统一使用 session_scope() 替代直接 async_session()
        async with cls.session_scope() as session:
            query = await session.scalars(select(model))
            return query.all()

    @classmethod
    async def query_by(cls, session: AsyncSession = None, **kwargs) -> List[M]:
        """
        通过字段查询（AND 条件），按创建时间排序。

        - 传入外部 session：在其上执行查询
        - 未传入 session：自动创建临时 session

        Args:
            session: 可选的外部会话对象
            **kwargs: 查询条件（filter_by 语义）

        Returns:
            List[M]: 匹配的模型实例列表
        """
        model = cls.__model__
        # 统一使用 session_scope 消除 if session 分支
        async with cls.session_scope(session) as session:
            query = await session.scalars(
                select(model).filter_by(**kwargs).order_by(model.create_time))
            return query.all()

    @classmethod
    async def query_by_in_clause(cls, target: str, list_: List[Any], session: AsyncSession = None) -> Sequence[M]:
        """
        根据指定字段和值列表查询数据（IN 子句）。

        Args:
            target: 模型中的字段名
            list_: 用于 IN 子句的值列表
            session: 可选的外部会话对象

        Returns:
            Sequence[M]: 查询结果列表

        Raises:
            CommonError: 字段名不存在时抛出
        """
        model = cls.__model__
        if not hasattr(model, target):
            raise CommonError("Invalid field name")

        stmt = select(model).where(getattr(model, target).in_(list_))
        # 统一使用 session_scope 消除 if session 分支
        async with cls.session_scope(session) as session:
            query = await session.scalars(stmt)
            return query.all()

    @staticmethod
    async def flush_expunge(session: AsyncSession, model: M, add: bool = False, refresh: bool = True) -> M:
        """
        刷新会话并分离模型
        :param session: 会话对象
        :param model: 模型实例
        :param add: 是否添加到会话
        :param refresh: 是否刷新模型
        :return: 模型实例
        """
        if add:
            session.add(model)
        await session.flush()
        if refresh:
            await session.refresh(model)
        session.expunge(model)
        return model

    @staticmethod
    async def add_flush_expunge(session: AsyncSession, model: M) -> M:
        """
        添加模型到会话，刷新并分离
        :param session: 会话对象
        :param model: 模型实例
        :return: 模型实例
        """
        return await Mapper.flush_expunge(session, model, add=True, refresh=True)

    @classmethod
    async def page_query(cls, current: int, pageSize: int, **kwargs):
        """
        分页查询。

        自动创建临时 session 执行 count + data 查询，完成后自动关闭。

        Args:
            current: 当前页码（从 1 开始）
            pageSize: 每页大小
            **kwargs: 查询条件和排序（支持 sort 参数）

        Returns:
            dict: 分页结果 {"items": [...], "pageInfo": {...}}
        """
        model = cls.__model__
        # 统一使用 session_scope() 替代直接 async_session()
        async with cls.session_scope() as session:
            sort = kwargs.pop("sort", None)
            conditions = await cls.search_conditions(**kwargs)
            base_query = select(model).filter(and_(*conditions))
            base_query = await cls.sorted_search(base_query, sort)

            total_query = select(func.count()).select_from(model).filter(*conditions)
            total = (await session.execute(total_query)).scalar()

            paginated_query = base_query.offset((current - 1) * pageSize).limit(pageSize)
            exe = await session.execute(paginated_query)
            data = exe.scalars().all()

            return await cls.map_page_data(data, total, pageSize, current)

    @classmethod
    async def get_creator(cls, creator_id: int, session: AsyncSession) -> User:
        """
        获取创建人信息
        :param creator_id: 创建人ID
        :param session: 会话对象
        :return: 用户对象
        """
        exe = await session.execute(select(User).where(User.id == creator_id))
        user = exe.scalar()
        if not user:
            raise NotFind("创建人信息不存在")
        return user

    @classmethod
    async def update_cls(
        cls, target: M, session: AsyncSession, *, expunge: bool = True, **kw
    ):
        """
        更新模型实例
        :param target: 目标模型实例
        :param session: 会话对象
        :param expunge: 是否在 flush 后从 session 分离 target. 默认 True 保持 M1 老行为.
                         M2 导回 commit 等"同一事务内多次 update + 后续 add_new"场景
                         应传 False, 避免 SQLAlchemy 异步 session 在 expunge + add_all
                         之间触发 "Can't operate on closed transaction inside context manager".
        :param kw: 更新字段
        :return: 更新后的模型实例
        """
        model = cls.__model__
        try:
            valid_columns = set(model.__table__.columns.keys())
            update_fields = {k: v for k, v in kw.items() if k in valid_columns}

            for field, value in update_fields.items():
                if hasattr(target, field):
                    setattr(target, field, value)

            await session.flush()
            if expunge:
                session.expunge(target)
            return target
        except Exception as e:
            raise

    @classmethod
    async def sorted_search(cls, base_query, sortInfo: str | Dict = None):
        """
        排序查询（默认按创建时间倒序）
        :param base_query: 基础查询
        :param sortInfo: 排序信息，支持JSON字符串或字典
        :return: 排序后的查询
        """
        model = cls.__model__
        sort = None
        try:
            if isinstance(sortInfo, str):
                sort = json.loads(sortInfo)
                if not isinstance(sort, dict):
                    raise ValueError("Invalid JSON format")
            elif isinstance(sortInfo, dict):
                sort = sortInfo
        except (TypeError, json.JSONDecodeError, ValueError):
            pass

        if sort:
            for k, v in sort.items():
                # 防御性校验：确保排序字段名存在于模型表中
                # 防止客户端传入非法排序字段（如 sortInfo='{"hacked_field": "descend"}'）
                # 导致 getattr(model, 'hacked_field') 抛出 AttributeError → 500
                if k not in model.__table__.columns:
                    raise CommonError(f"Invalid sort field: {k}")

                field = getattr(model, k)
                if v == "descend":
                    base_query = base_query.order_by(field.desc())
                else:
                    base_query = base_query.order_by(field.asc())
        else:
            base_query = base_query.order_by(model.create_time.desc())
        return base_query

    @classmethod
    async def search_conditions(cls, **kwargs) -> List:
        """
        构建查询条件
        支持的条件类型:
            - 精确匹配: field=value
            - 范围查询: field=[min, max]
            - 模糊查询: field="value" (自动添加 % 通配符)
            - None 判断: field=None
            - IN 查询: field__in=[1, 2, 3]
            - NOT IN 查询: field__not_in=[1, 2, 3]
            - 不等于: field__ne=value
            - 大于: field__gt=value
            - 大于等于: field__gte=value
            - 小于: field__lt=value
            - 小于等于: field__lte=value
            - LIKE 查询: field__like="%value%"
            - IS NOT NULL: field__is_not_null=True
        :param kwargs: 查询条件
        :return: 条件列表
        """
        conditions = []
        model = cls.__model__

        for key, value in kwargs.items():
            if "__" in key:
                field_name, operator = key.rsplit("__", 1)

                # 防御性校验：确保字段名存在于模型表中
                # 防止客户端传入非法字段名（如 {'hacked_field__gt': 5}）
                # 导致 getattr(model, 'hacked_field') 抛出 AttributeError → 500
                if field_name not in model.__table__.columns:
                    raise CommonError(f"Invalid field name: {field_name}")

                field = getattr(model, field_name)

                if operator == "in":
                    conditions.append(field.in_(value))
                elif operator == "not_in":
                    conditions.append(field.not_in(value))
                elif operator == "ne":
                    conditions.append(field != value)
                elif operator == "gt":
                    conditions.append(field > value)
                elif operator == "gte":
                    conditions.append(field >= value)
                elif operator == "lt":
                    conditions.append(field < value)
                elif operator == "lte":
                    conditions.append(field <= value)
                elif operator == "like":
                    conditions.append(field.like(value))
                elif operator == "ilike":
                    conditions.append(field.ilike(value))
                elif operator == "is_not_null":
                    if value:
                        conditions.append(field.is_not(None))
                elif operator == "is_null":
                    if value:
                        conditions.append(field.is_(None))
            else:
                # 防御性校验：确保字段名存在于模型表中
                if key not in model.__table__.columns:
                    raise CommonError(f"Invalid field name: {key}")

                field = getattr(model, key)
                if value is None:
                    conditions.append(field.is_(None))
                elif isinstance(value, tuple) and len(value) == 2:
                    conditions.append(and_(field >= value[0], field <= value[1]))
                elif isinstance(value, list):
                    conditions.append(field.in_(value))
                elif isinstance(value, str):
                    conditions.append(field.like(f"%{value}%"))
                elif isinstance(value, (int, float, bool)):
                    conditions.append(field == value)

        return conditions

    @classmethod
    async def map_page_data(cls, data: Sequence, total_num: int, page_size: int, current: int):
        """
        构建分页数据
        :param data: 数据列表
        :param total_num: 总记录数
        :param page_size: 每页大小
        :param current: 当前页码
        :return: 分页结果字典
        """
        return {
            "items": data,
            "pageInfo": {
                "total": total_num,
                "pages": calc_total_pages(total_num, page_size),
                "page": current,
                "limit": page_size
            }
        }

    @classmethod
    async def count_(cls) -> int:
        """
        统计记录数。

        自动创建临时 session 执行 count 查询，完成后自动关闭。

        Returns:
            int: 记录总数，异常时返回 0
        """
        model = cls.__model__
        try:
            # 统一使用 session_scope() 替代直接 async_session()
            async with cls.session_scope() as session:
                sql = select(func.count()).select_from(model)
                state = await session.execute(sql)
                return state.scalar()
        except Exception:
            return 0

    @classmethod
    async def tables(cls) -> List[str]:
        """
        获取数据库表名列表。

        自动创建临时 session 执行查询，完成后自动关闭。

        Returns:
            List[str]: 表名列表，异常时返回空列表
        """
        try:
            sql = """
                  SELECT TABLE_NAME AS table_name
                  FROM information_schema.TABLES
                  WHERE TABLE_SCHEMA = DATABASE() \
                  """
            # 统一使用 session_scope() 替代直接 async_session()
            async with cls.session_scope() as session:
                result = await session.execute(text(sql))
                return [row[0] for row in result.fetchall()]
        except Exception as e:
            log.exception(f"error: {e}")
            return []

    @classmethod
    async def page_by_module(
        cls,
        current: int,
        pageSize: int,
        module_type: int,
        module_id: int = None,
        module_ids: list = None,
        filter_field: str = "module_id",
        session: AsyncSession = None,
        **kwargs
    ):
        """
        按模块分页查询（支持树形模块结构 + 多模块联合查询）

        :param current: 当前页码
        :param pageSize: 每页大小
        :param module_type: 模块类型
        :param module_id: 单个模块ID（为空时查询全部）
        :param module_ids: 多个模块ID列表（与 module_id 互斥，module_ids 优先）；
                          会对每个 ID 展开各自的子节点后求并集过滤
        :param filter_field: 过滤字段名，默认 module_id
        :param session: 外部传入的数据库会话
        :param kwargs: 其他查询条件（支持 sort 排序参数）
        :return: 分页结果字典 {"items": [], "pageInfo": {...}}
        """
        from app.mapper.project.moduleMapper import get_subtree_ids

        model = cls.__model__
        sort_info = kwargs.pop("sort", None)
        offset = (current - 1) * pageSize

        async def _execute_query(sess: AsyncSession):
            # 多模块优先：把每个 module 各自展开成子节点后求并集
            subtree_ids = None
            if module_ids:
                merged: set = set()
                for mid in module_ids:
                    ids = await get_subtree_ids(sess, mid, module_type)
                    if ids:
                        merged.update(ids)
                subtree_ids = list(merged) if merged else None
            elif module_id:
                subtree_ids = await get_subtree_ids(sess, module_id, module_type)

            filter_column = getattr(model, filter_field)
            conditions = await cls.search_conditions(**kwargs)

            base_query = select(model)
            if subtree_ids:
                base_query = base_query.filter(filter_column.in_(subtree_ids))
            base_query = base_query.filter(and_(*conditions))
            base_query = await cls.sorted_search(base_query, sort_info)

            count_query = select(func.count()).select_from(model)
            if subtree_ids:
                count_query = count_query.filter(filter_column.in_(subtree_ids))
            count_query = count_query.filter(and_(*conditions))

            total = (await sess.execute(count_query)).scalar()
            data_query = base_query.offset(offset).limit(pageSize)
            data = (await sess.execute(data_query)).scalars().all()

            return await cls.map_page_data(data, total, pageSize, current)

        try:
            # 统一使用 session_scope(session) 消除 if session 分支：
            # - session 不为 None：复用它，在其上执行查询（不管理生命周期）
            # - session 为 None：session_scope() 自动创建临时 session，完成后自动关闭
            async with cls.session_scope(session) as sess:
                return await _execute_query(sess)
        except Exception as e:
            log.exception(f"page_by_module error: module_id={module_id}, module_ids={module_ids}, error={e}")
            return {"items": [], "pageInfo": {"total": 0, "pages": 0, "page": 0, "limit": page_size}}

    @classmethod
    async def _manage_session(cls, session: Optional[AsyncSession], model: M) -> M:
        """
        管理会话，统一通过 transaction(session) 处理事务边界。

        - 传入外部 session：直接在其上 add/flush/expunge，由调用方控制 commit
        - 未传入 session：自动创建 session + 事务，add/flush/expunge 后自动 commit

        Args:
            session: 可选的外部会话对象
            model: 待持久化的模型实例

        Returns:
            M: 已 flush + expunge 的模型实例（注意：已 detached，无法懒加载关联对象）
        """
        # 统一使用 transaction(session) 消除 if session is None 分支：
        # - session 不为 None：复用它，在其上执行操作（不擅自 commit）
        # - session 为 None：transaction() 自动创建新 session + begin，退出时自动 commit
        async with cls.transaction(session) as session:
            return await cls.add_flush_expunge(session, model)

    @classmethod
    async def bulk_insert(cls, items: List[Dict[str, Any]], session: AsyncSession = None) -> int:
        """
        批量插入数据（接受字典列表）。

        事务边界说明：
        - 传入外部 session：在其上 add_all 并 flush，由调用方控制 commit
        - 未传入 session：自动创建 session + 事务，add_all 后自动 commit

        Args:
            items: 数据字典列表
            session: 可选的外部会话对象

        Returns:
            int: 插入的记录数
        """
        if not items:
            return 0

        model = cls.__model__
        log.info(f"bulk_insert items: {items}")
        try:
            # 统一使用 transaction(session) 消除 if session 分支：
            # - session 不为 None：复用它，在其上执行操作并 flush（不擅自 commit）
            # - session 为 None：transaction() 自动创建新 session + begin，退出时自动 commit
            async with cls.transaction(session) as session:
                models = [model(**item) for item in items]
                log.info(f"bulk_insert models: {models}")
                session.add_all(models)
                await session.flush()
                return len(items)
        except Exception as e:
            log.exception(f"bulk_insert error: {e}")
            raise


    @classmethod
    async def bulk_insert_models(cls, models: List[M], session: AsyncSession = None) -> int:
        """
        批量插入模型实例（直接接受模型实例列表）。
        Args:
            models: 模型实例列表
            session: 必填的外部会话对象

        Returns:
            int: 插入的记录数
        """
        if session is None:
            # 强约束: 不再隐式开事务自 commit, 否则多张表批量无法同事务
            raise ValueError(
                "bulk_insert_models requires an external session "
                "(不再允许 session=None 隐式 commit)。"
                "如需自管理事务, 用 `async with async_session() as s, s.begin():` 后传入 s。"
            )
        if not models:
            return 0

        try:
            session.add_all(models)
            await session.flush()
            return len(models)
        except Exception as e:
            log.exception(f"bulk_insert_models error: {e}")
            raise

    @classmethod
    async def bulk_update(cls, updates: List[Dict[str, Any]], id_field: str = "id", session: AsyncSession = None) -> int:
        """
        批量更新数据。

        事务边界说明：
        - 传入外部 session：复用 session 执行所有 update 并 flush，由调用方控制 commit
          （适用于调用方需要在同一事务中批量更新多个表的场景）
        - 未传入 session：自动创建 session + 事务，执行所有 update 后自动 commit

        注意：本方法会从每个 update dict 中 pop 掉 id_field 指定的键。

        Args:
            updates: 更新数据列表，每项需包含 id_field 指定的字段
            id_field: 用于定位记录的字段名，默认为 "id"
            session: 可选的外部会话对象

        Returns:
            int: 实际执行更新的记录数（id 缺失的项会被跳过）
        """
        if not updates:
            return 0

        model = cls.__model__
        count = 0
        try:
            # 统一使用 transaction(session) 处理 session 和事务：
            # - session 不为 None：复用它，在其上执行操作并 flush（不擅自 commit）
            # - session 为 None：transaction() 自动创建新 session + begin，退出时自动 commit
            async with cls.transaction(session) as session:
                for item in updates:
                    ident = item.pop(id_field, None)
                    if ident is None:
                        continue
                    stmt = update(model).where(getattr(model, id_field) == ident).values(**item)
                    await session.execute(stmt)
                    count += 1
                # 外部 session 场景下：仅 flush，由调用方控制 commit
                # 内部 session 场景下：flush 后 transaction() 退出时自动 commit
                await session.flush()
                return count
        except Exception as e:
            log.exception(f"bulk_update error: {e}")
            raise

    @classmethod
    async def bulk_delete(cls, ids: List[int], session: AsyncSession = None) -> int:
        """
        批量删除数据。

        事务边界说明：
        - 传入外部 session：复用 session 执行 delete 并 flush，由调用方控制 commit
        - 未传入 session：自动创建 session + 事务，执行 delete 后自动 commit

        Args:
            ids: 要删除的 ID 列表
            session: 可选的外部会话对象

        Returns:
            int: 实际删除的记录数
        """
        if not ids:
            return 0

        model = cls.__model__
        stmt = delete(model).where(model.id.in_(ids))
        try:
            # 统一使用 transaction(session) 处理 session 和事务：
            # - session 不为 None：复用它，在其上执行操作并 flush（不擅自 commit）
            # - session 为 None：transaction() 自动创建新 session + begin，退出时自动 commit
            async with cls.transaction(session) as session:
                result = await session.execute(stmt)
                await session.flush()
                return result.rowcount
        except Exception as e:
            log.exception(f"bulk_delete error: {e}")
            raise

    @classmethod
    @asynccontextmanager
    async def transaction(cls, session: AsyncSession = None) -> AsyncGenerator[AsyncSession, None]:
        """
        事务上下文管理器。

        提供 session + 事务的统一管理：
        - 外部传入 session：复用它，不自动 begin/commit（由调用方控制事务边界）
        - 无外部 session：创建新 session + 自动 begin/commit/rollback

        典型用法（自管理事务，适用于简单写操作）：
            async with cls.transaction() as session:
                await session.execute(...)
                # 退出时自动 commit

        典型用法（在已有事务中复用，适用于复杂业务链）：
            async with cls.transaction() as outer_session:
                await cls.save(session=outer_session, ...)
                await cls.update_by_id(session=outer_session, ...)
                # 统一在 transaction() 退出时 commit

        Args:
            session: 可选的外部会话对象。传入时由调用方管理事务；
                     未传入时由本方法自动创建并管理事务。

        Yields:
            AsyncSession: 数据库会话
        """
        if session is not None:
            # 复用外部 session，调用方已自行管理事务（begin/commit/rollback）
            yield session
        else:
            # 自行创建 session，并通过 session.begin() 自动管理事务边界
            async with async_session() as session:
                async with session.begin():
                    yield session
