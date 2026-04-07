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
from typing import TypeVar, List, Type, Any, Optional, Generic, Dict, Union, Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text, delete, update

from app.exception import NotFind, CommonError
from app.model import async_session, BaseModel
from app.model.base import User
from utils import log


def calc_total_pages(total: int, page_size: int) -> int:
    """计算总页数"""
    if total == 0 or total is None:
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

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, '__model__'):
            raise TypeError(f"{cls.__name__} 必须定义 __model__ 类变量")

    @classmethod
    async def _execute_query(cls, stmt, session: Optional[AsyncSession] = None):
        """
        执行查询语句，自动处理会话管理
        :param stmt: 查询语句
        :param session: 可选的会话对象
        :return: 查询结果
        """
        if session is None:
            async with async_session() as session:
                return await session.execute(stmt)
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
            log.error(f"获取{cls.__name__}对象失败，{field_name}: {value}, 错误: {e}")
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
            log.error(f"保存{cls.__name__}失败: {e}")
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
            if session is None:
                async with async_session() as session:
                    instance = await session.get(model, ident)
            else:
                instance = await session.get(model, ident)

            if not instance:
                error_msg = f"数据{desc}不存在或已经删除，id: {ident}" if desc else f"数据不存在，id: {ident}"
                raise NotFind(error_msg)
            return instance
        except NotFind:
            raise
        except Exception as e:
            log.error(f"获取{cls.__name__}对象失败，id: {ident}, 错误: {e}")
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
    async def update_by_id(cls, session: AsyncSession = None, update_user: User = None, **kwargs) -> M:
        """
        通过id更新
        :param session: 可选的会话对象
        :param update_user: 更新人
        :param kwargs: 更新字段（必须包含id）
        :return: 更新后的模型实例
        """
        try:
            ident = kwargs.pop("id", None)
            if ident is None:
                raise ValueError("id parameter is required")

            kwargs = set_updater(update_user, **kwargs)

            if session is None:
                async with async_session() as session:
                    async with session.begin():
                        target = await cls.get_by_id(ident, session)
                        return await cls.update_cls(target, session, **kwargs)
            else:
                target = await cls.get_by_id(ident, session)
                await cls.update_cls(target, session, **kwargs)
                await session.commit()
                return target
        except Exception as e:
            log.exception(e)
            raise

    @classmethod
    async def update_by_uid(cls, update_user: User = None, **kwargs):
        """
        通过uid更新
        :param update_user: 更新人
        :param kwargs: 更新字段（必须包含uid）
        :return: 更新后的模型实例
        """
        kwargs = set_updater(update_user, **kwargs)

        try:
            async with async_session() as session:
                uid = kwargs.pop("uid")
                async with session.begin():
                    target = await cls.get_by_uid(uid, session)
                    return await cls.update_cls(target, session, **kwargs)
        except Exception as e:
            log.error(f"update_by_uid error: {e}")
            raise

    @classmethod
    async def delete_by_uid(cls, uid: str):
        """
        通过uid删除
        :param uid: uid
        """
        model = cls.__model__
        try:
            async with async_session() as session:
                await session.execute(delete(model).where(model.uid == uid))
                await session.commit()
        except Exception as e:
            log.exception(e)
            raise

    @classmethod
    async def delete_by_id(cls, ident: int, session: AsyncSession = None):
        """
        通过id删除
        :param ident: id
        :param session: 可选的会话对象
        """
        model = cls.__model__
        stmt = delete(model).where(model.id == ident)
        try:
            if session:
                await session.execute(stmt)
                await session.commit()
            else:
                async with async_session() as session:
                    await session.execute(stmt)
                    await session.commit()
        except Exception as e:
            log.exception(e)
            raise

    @classmethod
    async def delete_by(cls, session: AsyncSession, **kwargs):
        """
        通过属性删除
        :param session: 会话对象
        :param kwargs: 查询条件
        """
        try:
            model = await cls.get_by(session, **kwargs)
            if model:
                await session.delete(model)
                await session.flush()
                await session.commit()
        except Exception as e:
            log.error(f"delete_by error: {e}")
            raise

    @classmethod
    async def get_by(cls, session: AsyncSession = None, **kwargs) -> Optional[M]:
        """
        通过字段获取对象
        :param session: 可选的会话对象
        :param kwargs: 查询条件
        :return: 模型实例或None
        """
        model = cls.__model__
        sql = select(model).filter_by(**kwargs)
        try:
            if session is None:
                async with async_session() as session:
                    result = await session.scalars(sql)
            else:
                result = await session.scalars(sql)
            return result.first()
        except Exception as e:
            raise

    @classmethod
    async def query_all(cls) -> List[M]:
        """查询所有数据"""
        model = cls.__model__
        try:
            async with async_session() as session:
                query = await session.scalars(select(model))
                return query.all()
        except Exception as e:
            raise

    @classmethod
    async def query_by(cls, session: AsyncSession = None, **kwargs) -> List[M]:
        """
        通过字段查询（AND条件）
        :param kwargs: 查询条件
        :param session:
        :return: 查询结果列表
        """
        model = cls.__model__
        try:
            if session:
                query = await session.scalars(
                    select(model).filter_by(**kwargs).order_by(model.create_time))
            else:
                async with async_session() as session:
                    query = await session.scalars(
                        select(model).filter_by(**kwargs).order_by(model.create_time))
            return query.all()
        except Exception as e:
            raise

    @classmethod
    async def query_by_in_clause(cls, target: str, list_: List[Any], session: AsyncSession = None) -> Sequence[M]:
        """
        根据指定字段和值列表查询数据（IN子句）
        :param target: 模型中的字段名
        :param list_: 用于IN子句的值列表
        :param session: 可选的会话对象
        :return: 查询结果列表
        """
        model = cls.__model__
        if not hasattr(model, target):
            raise CommonError("Invalid field name")

        stmt = select(model).where(getattr(model, target).in_(list_))
        try:
            if session:
                query = await session.scalars(stmt)
                return query.all()
            else:
                async with async_session() as session:
                    query = await session.scalars(stmt)
                    return query.all()
        except Exception as e:
            raise

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
        return await Mapper.flush_expunge(session, model, add=True, refresh=False)

    @classmethod
    async def page_query(cls, current: int, pageSize: int, **kwargs):
        """
        分页查询
        :param current: 当前页码
        :param pageSize: 每页大小
        :param kwargs: 查询条件和排序
        :return: 分页结果
        """
        model = cls.__model__
        try:
            async with async_session() as session:
                sort = kwargs.pop("sort", None)
                conditions = await cls.search_conditions(**kwargs)
                base_query = select(model).filter(and_(*conditions))
                base_query = await cls.sorted_search(base_query,sort)

                total_query = select(func.count()).select_from(model).filter(*conditions)
                total = (await session.execute(total_query)).scalar()

                paginated_query = base_query.offset((current - 1) * pageSize).limit(pageSize)
                exe = await session.execute(paginated_query)
                data = exe.scalars().all()

                return await cls.map_page_data(data, total, pageSize, current)
        except Exception as e:
            raise

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
    async def update_cls(cls, target: M, session: AsyncSession, **kw):
        """
        更新模型实例
        :param target: 目标模型实例
        :param session: 会话对象
        :param kw: 更新字段
        :return: 更新后的模型实例
        """
        model = cls.__model__
        try:
            valid_columns = set(model.__table__.columns.keys())
            update_fields = {k: v for k, v in kw.items() if k in valid_columns}

            for field, value in update_fields.items():
                setattr(target, field, value)

            await session.flush()
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
                field = getattr(model, key)
                if value is None:
                    conditions.append(field.is_(None))
                elif isinstance(value, (tuple, list)) and len(value) == 2:
                    conditions.append(and_(field >= value[0], field <= value[1]))
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
        """统计记录数"""
        model = cls.__model__
        try:
            async with async_session() as session:
                sql = select(func.count()).select_from(model)
                state = await session.execute(sql)
                return state.scalar()
        except Exception:
            return 0

    @classmethod
    async def tables(cls) -> List[str]:
        """获取数据库表名列表"""
        try:
            sql = """
                  SELECT TABLE_NAME AS table_name
                  FROM information_schema.TABLES
                  WHERE TABLE_SCHEMA = DATABASE() \
                  """
            async with async_session() as session:
                result = await session.execute(text(sql))
                return [row[0] for row in result.fetchall()]
        except Exception as e:
            log.error(e)
            return []

    @classmethod
    async def page_by_module(
        cls,
        current: int,
        pageSize: int,
        module_type: int,
        module_id: int = None,
        filter_field: str = "module_id",
        session: AsyncSession = None,
        **kwargs
    ):
        """
        按模块分页查询（支持树形模块结构）

        :param current: 当前页码
        :param pageSize: 每页大小
        :param module_type: 模块类型
        :param module_id: 模块ID（为空时查询全部）
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
            subtree_ids = await get_subtree_ids(sess, module_id, module_type) if module_id else None

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
            if session:
                return await _execute_query(session)
            async with async_session() as sess:
                return await _execute_query(sess)
        except Exception as e:
            log.error(f"page_by_module error: module_id={module_id}, error={e}")
            return []

    @classmethod
    async def _manage_session(cls, session: Optional[AsyncSession], model: M) -> M:
        """
        管理会话，自动处理事务提交
        :param session: 可选的会话对象
        :param model: 模型实例
        :return: 模型实例
        """
        if session is None:
            async with async_session() as new_session:
                async with new_session.begin():
                    return await cls.add_flush_expunge(new_session, model)
        return await cls.add_flush_expunge(session, model)

    @classmethod
    async def bulk_insert(cls, items: List[Dict[str, Any]], session: AsyncSession = None) -> int:
        """
        批量插入数据
        :param items: 数据字典列表
        :param session: 可选的会话对象
        :return: 插入的记录数
        """
        if not items:
            return 0

        model = cls.__model__
        try:
            if session:
                session.add_all([model(**item) for item in items])
                await session.flush()
                return len(items)
            else:
                async with async_session() as session:
                    session.add_all([model(**item) for item in items])
                    await session.commit()
                    return len(items)
        except Exception as e:
            log.error(f"bulk_insert error: {e}")
            raise

    @classmethod
    async def bulk_update(cls, updates: List[Dict[str, Any]], id_field: str = "id", session: AsyncSession = None) -> int:
        """
        批量更新数据
        :param updates: 更新数据列表，每项需包含 id_field 指定的字段
        :param id_field: 用于定位记录的字段名
        :param session: 可选的会话对象
        :return: 更新的记录数
        """
        if not updates:
            return 0

        model = cls.__model__
        count = 0
        try:
            if session:
                for item in updates:
                    ident = item.pop(id_field, None)
                    if ident is None:
                        continue
                    stmt = update(model).where(getattr(model, id_field) == ident).values(**item)
                    await session.execute(stmt)
                    count += 1
                await session.flush()
                return count
            else:
                async with async_session() as session:
                    for item in updates:
                        ident = item.pop(id_field, None)
                        if ident is None:
                            continue
                        stmt = update(model).where(getattr(model, id_field) == ident).values(**item)
                        await session.execute(stmt)
                        count += 1
                    await session.commit()
                    return count
        except Exception as e:
            log.error(f"bulk_update error: {e}")
            raise

    @classmethod
    async def bulk_delete(cls, ids: List[int], session: AsyncSession = None) -> int:
        """
        批量删除数据
        :param ids: 要删除的ID列表
        :param session: 可选的会话对象
        :return: 删除的记录数
        """
        if not ids:
            return 0

        model = cls.__model__
        stmt = delete(model).where(model.id.in_(ids))
        try:
            if session:
                result = await session.execute(stmt)
                await session.flush()
                return result.rowcount
            else:
                async with async_session() as session:
                    result = await session.execute(stmt)
                    await session.commit()
                    return result.rowcount
        except Exception as e:
            log.error(f"bulk_delete error: {e}")
            raise

    @classmethod
    @asynccontextmanager
    async def transaction(cls):
        """
        事务上下文管理器
        :yield: 数据库会话
        """
        async with async_session() as session:
            async with session.begin():
                yield session
