#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/27
# @Author : cyq
# @File : testcaseMapper
# @Software: PyCharm
# @Desc: 测试用例数据访问层
from typing import List, Dict, Any, Optional

from sqlalchemy import select, insert, update, and_, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper import Mapper, set_creator
from app.mapper.test_case.requirementMapper import RequirementMapper
from app.mapper.test_case.testCaseStepMapper import TestCaseStepMapper
from app.mapper.test_case.caseDynamicMapper import CaseDynamicMapper, CaseDynamicRenderer
from app.model import async_session
from app.model.base import User
from app.model.caseHub.test_case import TestCase
from app.model.caseHub.test_case_step import TestCaseStep
from app.model.caseHub.association import RequirementCaseAssociation
from app.model.caseHub.case_step_dynamic import CaseStepDynamic
from utils import log


async def get_last_index(session: AsyncSession, requirement_id: int) -> int:
    """
    获取指定需求下用例的最大排序序号

    :param session: 数据库会话
    :param requirement_id: 需求ID
    :return: 最大排序序号，如果不存在则返回0
    """
    stmt = (
        select(RequirementCaseAssociation.order)
        .where(RequirementCaseAssociation.requirement_id == requirement_id)
        .order_by(RequirementCaseAssociation.order.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_case_index(session: AsyncSession, requirement_id: int, case_id: int) -> Optional[int]:
    """
    获取指定用例在需求下的排序序号

    :param session: 数据库会话
    :param requirement_id: 需求ID
    :param case_id: 用例ID
    :return: 排序序号
    """
    stmt = (
        select(RequirementCaseAssociation.order)
        .where(
            and_(
                RequirementCaseAssociation.requirement_id == requirement_id,
                RequirementCaseAssociation.case_id == case_id,
            )
        )
    )
    result = await session.execute(stmt)
    return result.scalar()


async def insert_requirement_case(session: AsyncSession, requirement_id: int, case_id: int):
    """
    将用例关联到需求，并更新需求的用例数量

    :param session: 数据库会话
    :param requirement_id: 需求ID
    :param case_id: 用例ID
    """
    last_order = await get_last_index(session, requirement_id)
    await session.execute(
        insert(RequirementCaseAssociation).values(
            requirement_id=requirement_id,
            case_id=case_id,
            order=last_order + 1
        )
    )
    req = await RequirementMapper.get_by_id(ident=requirement_id, session=session)
    req.case_number += 1


def _parse_steps(action: Optional[str], expected_result: Optional[str]) -> List[Dict[str, Optional[str]]]:
    """
    将按行分割的操作步骤和预期结果解析为步骤列表

    :param action: 操作步骤文本（按换行分割）
    :param expected_result: 预期结果文本（按换行分割）
    :return: 步骤字典列表
    """
    if action is None and expected_result is None:
        return [{"action": None, "expected_result": None}]

    act_lines = action.strip().split("\n") if action else None
    exp_lines = expected_result.strip().split("\n") if expected_result else None
    max_steps = max(len(act_lines) if act_lines else 0, len(exp_lines) if exp_lines else 0)

    return [
        {
            "action": act_lines[i] if act_lines and i < len(act_lines) else None,
            "expected_result": exp_lines[i] if exp_lines and i < len(exp_lines) else None,
        }
        for i in range(max_steps)
    ]


class TestCaseMapper(Mapper[TestCase]):
    __model__ = TestCase


    @classmethod
    async def case_info(cls,case_id:int):
        """
        获取指定用例的详细信息，包括步骤

        :param case_id: 用例ID
        :return: 用例详细信息字典
        """

        try:
            async with async_session() as session:
                case = await cls.get_by_id(ident=case_id, session=session)
                case_steps = await TestCaseStepMapper.query_sub_steps(case_id=case_id, session=session)
                return {
                    **case.to_dict(),
                    "case_sub_steps": case_steps,
                }
        except Exception as e:
            log.error(f"case_info error: case_id={case_id}, error={e}")
            raise

    @classmethod
    async def update_cases_common(cls, case_ids: List[int], project_id: int, module_id: int):
        """
        批量将用例设为公共用例库

        :param case_ids: 用例ID列表
        :param project_id: 目标项目ID
        :param module_id: 目标模块ID
        """
        try:
            async with cls.transaction() as session:
                await session.execute(
                    update(cls.__model__)
                    .where(cls.__model__.id.in_(case_ids))
                    .values(
                        is_common=True,
                        project_id=project_id,
                        module_id=module_id,
                    )
                )
        except Exception:
            log.exception("update_cases_common 异常")
            raise

    @classmethod
    async def _update_association_field(
            cls,
            case_ids: List[int],
            field_name: str,
            new_value: Any,
            old_field_name: str,
            user: User
    ):
        """
        批量更新关联表字段并记录变更动态（内部方法）

        :param case_ids: 用例ID列表
        :param field_name: 要更新的字段名
        :param new_value: 新值
        :param old_field_name: 变更前数据中对应的字段名
        :param user: 操作用户
        """
        try:
            async with cls.transaction() as session:
                stmt = select(RequirementCaseAssociation).where(
                    RequirementCaseAssociation.case_id.in_(case_ids)
                )
                assoc_list = (await session.execute(stmt)).scalars().all()

                for assoc in assoc_list:
                    old_value = getattr(assoc, old_field_name, None)
                    await CaseDynamicMapper.update_dynamic(
                        case_id=assoc.case_id,
                        old_case={old_field_name: old_value},
                        new_case={old_field_name: new_value},
                        session=session,
                        cr=user
                    )

                field = getattr(RequirementCaseAssociation, field_name)
                await session.execute(
                    update(RequirementCaseAssociation)
                    .where(RequirementCaseAssociation.case_id.in_(case_ids))
                    .values({field_name: new_value})
                )
        except Exception as e:
            log.error(f"_update_association_field error: case_ids={case_ids}, field={field_name}, error={e}")
            raise



    @classmethod
    def _prepare_case_data(
            cls,
            case_data: Dict[str, Any],
            project_id: int,
            module_id: Optional[int],
            user: User,
            is_common: bool
    ) -> TestCase:
        """
        准备单个用例数据

        :param case_data: 用例原始数据
        :param project_id: 项目ID
        :param module_id: 模块ID
        :param user: 操作用户
        :param is_common: 是否公共用例
        :return: 用例模型实例
        """
        case_data.pop("action", None)
        case_data.pop("expected_result", None)
        # group_path 是解析阶段预留给 UploadModuleResolver 的字段,
        # 已经在 insert_upload_case 里解析成 module_id, 这里必须弹出
        case_data.pop("group_path", None)
        case_data.update({
            "project_id": project_id,
            "module_id": module_id,
            "creator": user.id,
            "creatorName": user.username,
            "is_common": is_common,
        })
        return cls.__model__(**case_data)

    @classmethod
    def _prepare_steps(
            cls,
            action: Optional[str],
            expected_result: Optional[str],
            case_index: int,
            user: User
    ) -> List[Dict[str, Any]]:
        """
        准备用例步骤数据

        :param action: 操作步骤文本
        :param expected_result: 预期结果文本
        :param case_index: 用例索引
        :param user: 操作用户
        :return: 步骤数据字典列表
        """
        steps = _parse_steps(action, expected_result)
        result = []
        for step_index, step_data in enumerate(steps):
            step_data.update({
                "test_case_index": case_index,
                "order": step_index,
                "creator": user.id,
                "creatorName": user.username,
            })
            result.append(step_data)
        return result

    @classmethod
    def _prepare_requirement_associations(
            cls,
            case_index: int,
            requirement_id: int,
            last_order: int,
            case_data: Dict[str, Any]
    ) -> RequirementCaseAssociation:
        """
        准备需求关联数据

        :param case_index: 用例临时索引 (flush 前无真实 id, flush 后用 case_id_map 替换)
        :param requirement_id: 需求ID
        :param last_order: 当前最大排序号, 由调用方维护累加器
            (用累加器而非每次查 max(order) 是为了避免 N 次 round-trip;
             累加器初值来自一次性的 get_last_index 查询)
        :param case_data: 用例数据 (仅取 case_type / case_status)
        :return: 需求用例关联模型
        """
        return RequirementCaseAssociation(
            requirement_id=requirement_id,
            case_id=case_index,
            order=last_order + 1,
            is_review=0,
            case_type=case_data.get("case_type", None),
            case_status=case_data.get("case_status", None),
        )

    @classmethod
    async def insert_upload_case(
            cls,
            cases: List[Dict[str, Any]],
            project_id: int,
            user: User,
            module_id: Optional[int] = None,
            requirement_id: Optional[int] = None,
            is_common: bool = True,
    ) -> int:
        """
        从Excel批量导入用例

        处理流程：
        1. 批量插入用例记录
        2. 解析步骤并关联到用例
        3. 关联需求（如有）并更新需求用例数量
        4. 记录用例动态

        :param cases: 用例数据列表
        :param project_id: 项目ID
        :param module_id: 模块ID（可选）
        :param requirement_id: 需求ID（可选）
        :param user: 操作用户
        :param is_common: 是否公共用例
        :return: 导入的用例数量
        """
        if not cases:
            return 0

        # 预解析 group_path -> module_id (在事务外, 避免嵌套事务破坏原子性)
        # - 先 dedupe paths: N 条 case 经常只有 K 个 unique path (K << N)
        # - 每个 unique path 只 resolve 一次, 大幅减少 find_or_create_path 调用
        # - 失败的回退到入参 module_id
        from utils.caseEnumResolver import resolve_group_path, _split_group_path
        case_module_map: Dict[int, int] = {}
        unique_path_resolved: Dict[str, Optional[int]] = {}
        for case_index, case_data in enumerate(cases):
            raw_path = case_data.get("group_path")
            if not raw_path:
                continue
            # 用拆分后的 tuple 当 cache key.
            # 同一原始字符串可能有多种写法 (e.g. "a/b/" vs "a/b"), tuple 形态能 dedupe
            titles = _split_group_path(raw_path)
            # 0x1f = Unit Separator, ASCII 控制符, 业务字符串中不可能出现, 用作连接符安全无歧义
            cache_key = "\x1f".join(titles)
            if cache_key not in unique_path_resolved:
                unique_path_resolved[cache_key] = await resolve_group_path(
                    project_id=project_id,
                    raw_group_path=raw_path,
                    user=user,
                )
            resolved = unique_path_resolved[cache_key]
            if resolved is not None:
                case_module_map[case_index] = resolved

        log.info(f"开始导入用例，共 {len(cases)} 条")
        async with cls.transaction() as session:
            case_objects = []
            all_steps = []
            requirement_associations = []
            last_order = await get_last_index(session, requirement_id) if requirement_id else 0

            for case_index, case_data in enumerate(cases):
                effective_module_id = case_module_map.get(case_index, module_id)
                case_obj = cls._prepare_case_data(
                    case_data=case_data.copy(),
                    project_id=project_id,
                    module_id=effective_module_id,
                    user=user,
                    is_common=is_common
                )
                case_objects.append(case_obj)

                steps = cls._prepare_steps(
                    action=case_data.get("action"),
                    expected_result=case_data.get("expected_result"),
                    case_index=case_index,
                    user=user
                )
                all_steps.extend(steps)

                if requirement_id:
                    assoc = cls._prepare_requirement_associations(
                        case_index=case_index,
                        requirement_id=requirement_id,
                        last_order=last_order,
                        case_data=case_data
                    )
                    requirement_associations.append(assoc)
                    last_order += 1

            session.add_all(case_objects)
            await session.flush()

            case_id_map = {i: case_obj.id for i, case_obj in enumerate(case_objects)}

            step_objects = [
                TestCaseStepMapper.__model__(**cls._map_step_id(step_data, case_id_map))
                for step_data in all_steps
            ]
            session.add_all(step_objects)

            if requirement_associations:
                for assoc in requirement_associations:
                    assoc.case_id = case_id_map[assoc.case_id]
                session.add_all(requirement_associations)

                req = await RequirementMapper.get_by_id(ident=requirement_id, session=session)
                req.case_number += len(case_objects)

            log.info(f"成功导入用例 {len(case_objects)} 条")
            return len(case_objects)

    @staticmethod
    def _map_step_id(step_data: Dict[str, Any], case_id_map: Dict[int, int]) -> Dict[str, Any]:
        """将步骤的临时索引替换为实际用例ID"""
        case_index = step_data.pop("test_case_index")
        step_data["test_case_id"] = case_id_map[case_index]
        return step_data

    @classmethod
    async def remove_case(cls, caseId: int, requirement_id: Optional[int]):
        """
        删除测试用例

        :param caseId: 用例ID
        :param requirement_id: 需求ID（可选，用于更新需求用例数量）
        """
        try:
            async with cls.transaction() as session:
                case_obj: TestCase = await cls.get_by_id(ident=caseId, session=session)

                if case_obj.is_common and requirement_id:
                    req = await RequirementMapper.get_by_id(ident=requirement_id, session=session)
                    if req.case_number > 0:
                        req.case_number -= 1
                    await session.execute(
                        delete(RequirementCaseAssociation).where(
                            and_(
                                RequirementCaseAssociation.requirement_id == requirement_id,
                                RequirementCaseAssociation.case_id == caseId
                            )
                        )
                    )
                else:
                    await session.execute(
                        delete(cls.__model__).where(cls.__model__.id == caseId)
                    )
        except Exception as e:
            log.error(f"remove_case error: caseId={caseId}, requirement_id={requirement_id}, error={e}")
            raise

    @classmethod
    async def query_case_by_field(cls, requirement_id: int, **kwargs):
        """
        根据条件过滤查询用例

        :param requirement_id: 需求ID
        :param kwargs: 过滤条件
            - TestCase字段: case_name, case_tag
            - RequirementCaseAssociation字段: is_review, case_status, case_type, case_level
        :return: 符合条件的用例列表（包含关联表的 is_review 和 case_status）
        """
        ASSOCIATION_FIELDS = {'is_review', 'case_status', 'case_type', 'case_level'}

        case_filters = {k: v for k, v in kwargs.items() if k not in ASSOCIATION_FIELDS}
        association_filters = {k: v for k, v in kwargs.items() if k in ASSOCIATION_FIELDS}

        try:
            async with async_session() as session:
                case_conditions = await cls.search_conditions(**case_filters)

                query = (
                    select(TestCase,
                           RequirementCaseAssociation.is_review,
                           RequirementCaseAssociation.case_status,
                           RequirementCaseAssociation.case_type,
                           RequirementCaseAssociation.case_level)
                    .join(RequirementCaseAssociation, RequirementCaseAssociation.case_id == TestCase.id)
                    .where(RequirementCaseAssociation.requirement_id == requirement_id)
                )

                if case_conditions:
                    query = query.where(and_(*case_conditions))

                for field_name, value in association_filters.items():
                    if hasattr(RequirementCaseAssociation, field_name):
                        field = getattr(RequirementCaseAssociation, field_name)
                        if value is None:
                            query = query.where(field.is_(None))
                        elif isinstance(value, (int, float, bool)):
                            query = query.where(field == value)
                        elif isinstance(value, str):
                            query = query.where(field.like(f"%{value}%"))
                        else:
                            query = query.where(field == value)

                query = query.order_by(RequirementCaseAssociation.order)

                result = await session.execute(query)
                rows = result.all()

                return [
                    {
                        **(row[0].to_dict()),
                        "is_review": row[1],
                        "case_status": row[2],
                        "case_type": row[3],
                        "case_level": row[4],

                    }
                    for row in rows
                ]

        except Exception as e:
            log.exception(f"query_case_by_field error: requirement_id={requirement_id}, kwargs={kwargs}, error={e}")
            raise

    @classmethod
    async def query_tags(cls, requirement_id: int):
        """
        获取需求下所有用例的标签集合

        :param requirement_id: 需求ID
        :return: 标签集合
        """
        try:
            async with async_session() as session:
                tags = await session.scalars(
                    select(TestCase.case_tag)
                    .join(RequirementCaseAssociation, RequirementCaseAssociation.case_id == TestCase.id)
                    .where(
                        RequirementCaseAssociation.requirement_id == requirement_id,
                        TestCase.case_tag.isnot(None)
                    )
                )
                # debug 级别: 标签通常很少, 仅调试时打开; 原 info 会把所有 tag 刷到日志
                log.debug(f"query_tags: requirement_id={requirement_id}, tag_count={len(all_tags)}")
                return set(all_tags) if all_tags else []
        except Exception as e:
            log.error(f"query_tags error: requirement_id={requirement_id}, error={e}")
            raise

    @classmethod
    async def save_case(cls, user: User, requirement_id: Optional[int] = None, **kwargs):
        """
        创建测试用例及其步骤

        :param user: 创建者用户
        :param requirement_id: 关联的需求ID（可选）
        :param kwargs: 用例字段数据
        :return: 创建的用例对象
        """
        case_sub_steps = kwargs.pop("case_sub_steps", [])

        kwargs = set_creator(user, **kwargs)

        try:
            async with cls.transaction() as session:
                case_obj: TestCase = await cls.save(session=session, **kwargs)

                if case_sub_steps:
                    steps = [TestCaseStep(
                        **i,
                        test_case_id=case_obj.id,
                        creator=user.id,
                        creatorName=user.username
                    )  for i in case_sub_steps]
                    session.add_all(steps)

                if requirement_id:
                    await insert_requirement_case(
                        session=session,
                        requirement_id=requirement_id,
                        case_id=case_obj.id
                    )
       
                await CaseDynamicMapper.new_dynamic(
                    cr=user,
                    test_case=case_obj,
                    session=session
                )

                return case_obj
        except Exception as e:
            log.error(f"save_case error: kwargs={kwargs}, error={e}")
            raise
    
    @classmethod
    async def delete_batch_cases(cls, delete_case_list: List[int]) -> int:
        """
        批量删除测试用例及其关联数据

        高性能策略：
        1. 单次 DELETE 删除关联表记录（步骤、需求关联）
        2. 单次 DELETE 删除用例主表
        3. 批量记录删除动态

        :param delete_case_list: 用例ID列表
        :return: 删除的用例数量
        """
        if not delete_case_list:
            return 0
        try:
            async with cls.transaction() as session:
             
                case_stmt = delete(TestCase).where(TestCase.id.in_(delete_case_list))
                result = await session.execute(case_stmt)
                delete_count = result.rowcount
                log.info(f"批量删除成功: 删除{delete_count}条用例")
                return delete_count

        except Exception as e:
            log.error(f"delete_batch_cases error: ids={delete_case_list}, error={e}")
            raise
    
    @classmethod
    async def update_batch_cases(cls, update_case_list: List[int], user: User, **kwargs):
        """
        批量更新测试用例信息，并记录变更动态

        使用高性能的批量更新策略：
        1. 单次 UPDATE 语句更新所有记录
        2. 批量获取更新前的数据
        3. 批量记录变更动态

        :param update_case_list: 用例ID列表
        :param user: 更新者用户
        :param kwargs: 更新字段数据（排除id）
        """
        if not update_case_list or not kwargs:
            return 0

        log.info(f"批量更新用例: ids={update_case_list}, fields={kwargs}")

        try:
            async with cls.transaction() as session:
                old_cases_stmt = select(TestCase).where(TestCase.id.in_(update_case_list))
                old_cases_result = await session.execute(old_cases_stmt)
                old_cases_list = old_cases_result.scalars().all()

                if not old_cases_list:
                    log.warning(f"未找到要更新的用例: {update_case_list}")
                    return 0

                old_cases_map = {case.id: case.map for case in old_cases_list}

                stmt = update(TestCase).where(TestCase.id.in_(update_case_list))
                update_fields = {k: v for k, v in kwargs.items() if k != 'id'}
                stmt = stmt.values(**update_fields)
                result = await session.execute(stmt)
                log.info(f"批量更新影响行数: {result.rowcount}")

                new_cases_stmt = select(TestCase).where(TestCase.id.in_(update_case_list))
                new_cases_result = await session.execute(new_cases_stmt)
                new_cases_list = new_cases_result.scalars().all()

                dynamic_records = []
                renderer = await CaseDynamicRenderer.from_db(session=session)
                for new_case in new_cases_list:
                    old_data = old_cases_map.get(new_case.id, {})
                    new_data = new_case.map

                    if old_data != new_data:
                        diff_info = renderer.diff_dict(old_data, new_data)
                        if diff_info:
                            dynamic_records.append(
                                CaseStepDynamic(
                                    description=f"{user.username} 批量更新了测试用例 :{diff_info}",
                                    test_case_id=new_case.id,
                                    creator=user.id,
                                    creatorName=user.username
                                )
                            )

                if dynamic_records:
                    session.add_all(dynamic_records)
                    await session.flush()

                log.info(f"批量更新成功: 更新{result.rowcount}条, 记录{len(dynamic_records)}条动态")
                return result.rowcount

        except Exception as e:
            log.error(f"update_batch_cases error: ids={update_case_list}, kwargs={kwargs}, error={e}")
            raise
    
    @classmethod
    async def update_case(cls, ur: User, **kwargs):
        """
        更新测试用例信息，并记录变更动态

        :param ur: 更新者用户
        :param kwargs: 更新字段数据（必须包含id）
        """
        log.info(f"更新用例参数: {kwargs}")

        try:
            async with async_session() as session:
                async with session.begin():
                    case_obj = await cls.get_by_id(ident=kwargs.get("id"), session=session)
                    old_data = case_obj.map
                    kwargs.pop("id", None)
                    new_case = await cls.update_cls(case_obj, session, **kwargs)

                    await CaseDynamicMapper.update_dynamic(
                        cr=ur,
                        case_id=case_obj.id,
                        old_case=old_data,
                        new_case=new_case.map,
                        session=session
                    )
        except Exception as e:
            log.error(f"update_case error: kwargs={kwargs}, error={e}")
            raise

    @classmethod
    async def _fetch_source_cases_and_steps(cls, case_ids: List[int], session: AsyncSession) -> tuple:
        """
        获取源用例及其步骤（内部方法）

        :param case_ids: 用例ID列表
        :param session: 数据库会话
        :return: (源用例列表, 步骤映射字典)
        """
        source_cases = await cls.query_by_in_clause("id", case_ids, session)

        source_steps_map = {}
        if source_cases:
            steps_result = await session.execute(
                select(TestCaseStep)
                .where(TestCaseStep.test_case_id.in_(case_ids))
                .order_by(TestCaseStep.order)
            )
            all_steps = steps_result.scalars().all()
            for step in all_steps:
                source_steps_map.setdefault(step.test_case_id, []).append(step)

        return source_cases, source_steps_map

    @classmethod
    def _build_new_cases(
            cls,
            source_cases,
            source_steps_map: dict,
            user: User
    ) -> List[TestCase]:
        """
        构建新的用例副本（内部方法）

        :param source_cases: 源用例列表
        :param source_steps_map: 步骤映射字典
        :param user: 操作用户
        :return: 新用例列表
        """
        new_case_list = []
        for source_case in source_cases:
            new_case_data = source_case.copy_map()
            new_case_data["case_name"] += " - 副本"
            new_case_data["creator"] = user.id
            new_case_data["creatorName"] = user.username
            new_case_model = TestCase(**new_case_data)

            steps = source_steps_map.get(source_case.id, [])
            new_case_model.case_sub_steps = [
                TestCaseStep(
                    **{
                        **step.copy_map(),
                        "test_case_id": new_case_model.id,
                        "creator": user.id,
                        "creatorName": user.username
                    }
                )
                for step in steps
            ]
            new_case_list.append(new_case_model)

        return new_case_list

    @classmethod
    async def _create_requirement_associations(
            cls,
            new_case_list: List[TestCase],
            requirement_id: int,
            session: AsyncSession
    ):
        """
        创建需求关联记录（内部方法）

        :param new_case_list: 新用例列表
        :param requirement_id: 需求ID
        :param session: 数据库会话
        """
        req = await RequirementMapper.get_by_id(ident=requirement_id, session=session)
        req.case_number += len(new_case_list)

        max_order_result = await session.execute(
            select(func.max(RequirementCaseAssociation.order))
            .where(RequirementCaseAssociation.requirement_id == requirement_id)
        )
        max_order = max_order_result.scalar() or 0

        assoc_values = [
            {
                "requirement_id": requirement_id,
                "case_id": new_case_obj.id,
                "order": max_order + idx + 1
            }
            for idx, new_case_obj in enumerate(new_case_list)
        ]
        await session.execute(insert(RequirementCaseAssociation).values(assoc_values))

    @classmethod
    async def copy_cases(cls, case_ids: List[int], user: User, requirement_id: Optional[int]=None, session: Optional[AsyncSession]=None):
        """
        复制用例及其步骤

        :param case_ids: 被复制的源用例ID列表
        :param user: 操作用户
        :param requirement_id: 目标需求ID（可选）
        :param session: 异步会话（可选）
        :return: 复制的用例对象
        """
        try:
            async with cls.session_scope(session) as session:
                source_cases, source_steps_map = await cls._fetch_source_cases_and_steps(case_ids, session)

                new_case_list = cls._build_new_cases(source_cases, source_steps_map, user)

                session.add_all(new_case_list)
                await session.flush()

                if requirement_id and source_cases:
                    await cls._create_requirement_associations(new_case_list, requirement_id, session)

                for new_case_obj in new_case_list:
                    await CaseDynamicMapper.new_dynamic(
                        cr=user,
                        test_case=new_case_obj,
                        session=session
                    )

                return new_case_list
        except Exception as e:
            log.error(f"copy_cases error: case_ids={case_ids}, requirement_id={requirement_id}, error={e}")
            raise

    @classmethod
    async def add_next_case(cls, requirement_id: int, case_id: int, user: User):
        """
        在当前用例后快速创建下一条用例（复制）

        ⚠ TODO(known issue): 当前实现存在短板:
        - 新建的 case 没有关联到 requirement (RequirementCaseAssociation 未插)
        - order 未设置 (不会出现在需求的用例列表)
        - 步骤 case_sub_steps 未拷贝 (用例是空壳)
        - 操作动态 CaseDynamicMapper 未记录
        今后如果调用方依赖事件发生改变, 请及时修复.

        :param requirement_id: 需求ID
        :param case_id: 当前用例ID
        :param user: 操作用户
        """
        try:
            async with cls.transaction() as session:
                req = await RequirementMapper.get_by_id(ident=requirement_id, session=session)
                current_case = await cls.get_by_id(ident=case_id, session=session)

                new_case = await cls._copy_case_data(
                    source=current_case,
                    user=user,
                    session=session
                )

                req.case_number += 1
                await cls.add_flush_expunge(session=session, model=new_case)
        except Exception as e:
            log.error(f"add_next_case error: requirement_id={requirement_id}, case_id={case_id}, error={e}")
            raise

    @classmethod
    async def _copy_case_data(cls, source: TestCase, user: User, session: AsyncSession) -> TestCase:
        """
        复制用例数据（内部方法）

        :param source: 源用例对象
        :param user: 操作用户
        :param session: 数据库会话
        :return: 新的用例对象
        """
        new_data = source.copy_map()
        new_data["case_name"] += " - 副本"
        new_data["creator"] = user.id
        new_data["creatorName"] = user.username
        return await cls.save(session=session, **new_data)

    @classmethod
    async def add_default_case(cls, requirement_id: int, user: User):
        """
        在需求下添加一条默认模板用例

        流程:
        1. 需求 case_number +1 (新加一条占位)
        2. 用 TestCase.set_default 初始化一个空壳用例
        3. module_id / project_id 继承自需求
        4. flush 取真实 id 后, 在 RequirementCaseAssociation 里建关联
           (order = 当前 max + 1, 追加到末尾)

        :param requirement_id: 需求ID
        :param user: 操作用户
        """
        try:
            async with cls.transaction() as session:
                req = await RequirementMapper.get_by_id(ident=requirement_id, session=session)
                req.case_number += 1

                new_case = TestCase()
                await new_case.set_default(user)
                new_case.module_id = req.module_id
                new_case.project_id = req.project_id

                await cls.add_flush_expunge(session=session, model=new_case)
                last_order = await get_last_index(session, requirement_id)
                await session.execute(
                    insert(RequirementCaseAssociation).values(
                        requirement_id=requirement_id,
                        case_id=new_case.id,
                        order=last_order + 1
                    )
                )
        except Exception as e:
            log.error(f"add_default_case error: requirement_id={requirement_id}, error={e}")
            raise
        
