#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/8/27
# @Author : cyq
# @File : testCaseSchema
# @Software: PyCharm
# @Desc: 测试用例相关的Schema定义
from typing import List, Literal, Optional,Dict,Any

from pydantic import BaseModel, Field

from app.schema import PageSchema
from enums import ModuleEnum
from enums.CaseEnum import CaseLevel


class TestCaseStep(BaseModel):
    """测试用例步骤模型"""
    order: Optional[int] = Field(None, description="顺序")
    action: Optional[str] = Field(None, description="操作步骤")
    expected_result: Optional[str] = Field(None, description="预期结果")
    id: Optional[int] = Field(None, description="步骤ID")


class TestCaseField(BaseModel):
    """测试用例基础字段模型"""
    case_name: Optional[str] = Field(None, description="用例名称")
    case_level: Optional[str] = Field(None, description="用例级别")
    case_type: Optional[str] = Field(None, description="用例类型")
    case_platform: Optional[str] = Field(None, description="用例平台")
    case_tag: Optional[str] = Field(None, description="用例标签")
    case_setup: Optional[str] = Field(None, description="用例前置条件")
    case_mark: Optional[str] = Field(None, description="用例备注")
    is_common: Optional[bool] = Field(False, description="是否公共用例")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")

    case_sub_steps: Optional[List[TestCaseStep]] = Field(None, description="用例子步骤")


class AddTestCaseSchema(TestCaseField):
    """添加测试用例模型"""
    requirement_id: Optional[int] = Field(None, description="需求ID")
    case_name: str = Field(..., description="用例名称")
    case_tag: str = Field(..., description="用例标签")
    case_mark: Optional[str] = Field(None, description="用例备注")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: int = Field(..., description="项目ID")

class AddPlanCaseSchema(TestCaseField):
    """添加计划关联的用例模型"""
    plan_id: int = Field(..., description="计划ID")
    plan_module_id: Optional[int] = Field(None, description="计划分组ID，NULL表示未分组")
    case_name: str = Field(..., description="用例名称")
    case_tag: str = Field(..., description="用例标签")
    case_mark: Optional[str] = Field(None, description="用例备注")
    module_id: Optional[int] = Field(None, description="模块ID")




class UpdatePlanCaseSchema(BaseModel):
    """更新计划关联的用例模型"""
    plan_id: Optional[int] = Field(None, description="计划ID")
    plan_module_id: Optional[int] = Field(None, description="计划分组ID，NULL表示未分组")
    case_ids: Optional[List[int]] = Field(None, description="用例ID列表")


class UpdateTestCaseSchema(TestCaseField):
    id: int = Field(..., description="ID")

class UpdateTestCasesSchema(TestCaseField):
    """更新测试用例模型"""
    update_case_list: List[int] = Field(..., description="更新用例ID列表")

class DeleteTestCasesSchema(BaseModel):
    """删除测试用例模型"""
    delete_case_list: List[int] = Field(..., description="删除用例ID列表")


class InsertMindCaseSchema(BaseModel):
    """插入思维导图用例模型

    脑图归属两种模式：
    - 按需求：传 requirement_id（保留兼容老入口，已弱化）
    - 按计划：传 plan_id（推荐，新流程主入口）
    """
    mind_node: dict = Field(..., description="思维导图节点")
    plan_id: Optional[int] = Field(None, description="计划ID（按计划维度时填写）")
    requirement_id: Optional[int] = Field(None, description="需求ID（按需求维度时填写）")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")


class UpdateMindCaseSchema(BaseModel):
    """更新思维导图用例模型"""
    mind_node: Optional[dict] = Field(None, description="思维导图节点")
    id: int = Field(..., description="用例ID")
    plan_id: Optional[int] = Field(None, description="计划ID")
    module_id: Optional[int] = Field(None, description="模块ID")
    project_id: Optional[int] = Field(None, description="项目ID")


class QueryMindCaseSchema(BaseModel):
    """查询脑图详情入参

    plan_id 和 requirement_id 二选一，同时传时 plan_id 优先。
    """
    plan_id: Optional[int] = Field(None, description="计划ID")
    requirement_id: Optional[int] = Field(None, description="需求ID")




class PageTestCaseSchema(PageSchema, TestCaseField):
    """测试用例分页查询模型"""
    module_type: int = Field(ModuleEnum.CASE, description="模块类型")
    case_level: Optional[str] = Field(None, description="用例级别")
    case_type: Optional[str] = Field(None, description="用例类型")
    case_status: Optional[int] = Field(None, description="用例状态")
    is_review: Optional[str] = Field(None, description="是否审核 0:未审核 1:已审核")
    # 多模块查询：与 module_id 互斥；同时传入时 module_ids 优先
    # 用于支持前端多选目录时按多个模块（含各自子节点）联合过滤
    module_ids: Optional[List[int]] = Field(None, description="模块ID列表（多选）")


class QueryTestCaseSchemaByReq(BaseModel):
    """根据需求ID查询测试用例模型"""
    requirement_id: int = Field(..., description="需求ID")


class AddDefaultCaseSchema(QueryTestCaseSchemaByReq):
    """添加默认用例模型"""
    pass


class AddNextCaseSchema(BaseModel):
    """添加默认用例模型"""
    current_case_id: int = Field(..., description="当前caseID")


class QueryTestCaseSchemaByField(BaseModel):
    """根据字段查询测试用例模型"""
    requirement_id: int = Field(..., description="需求ID")
    case_name: Optional[str] = Field(None, description="用例名称")
    case_level: Optional[str] = Field(None, description="用例级别")
    case_type: Optional[int] = Field(None, description="用例类型")
    case_tag: Optional[str] = Field(None, description="用例标签")
    case_status: Optional[int] = Field(None, description="用例状态")
    is_review: Optional[int] = Field(None, description='是否评审 0:未评审 1:已评审')
    is_common: Optional[bool] = Field(None, description='是否公共')


class CopyCase(BaseModel):
    """复制用例模型"""
    caseId: int = Field(..., description="用例ID")
    requirement_id: Optional[int] = Field(None, description="需求ID")


class RemoveCaseSchema(BaseModel):
    """删除用例模型"""
    caseId: int = Field(..., description="用例ID")
    requirement_id: Optional[int] = Field(None, description="需求ID")


class CopyCaseStep(BaseModel):
    """复制用例步骤模型"""
    step_id: int = Field(..., description="步骤ID")


class ReorderCase(BaseModel):
    """重排序用例模型（需求维度, 旧版, 传全量 case_ids 列表）

    已被下面 module 维度的 ReorderTestCaseSchema 替代, 但 schema 留作兼容
    """
    requirement_id: int = Field(..., description="需求ID")
    case_ids: List[int] = Field(..., description="用例ID列表")


class ReorderTestCaseItem(BaseModel):
    """单条重排序意图（用于批量接口）

    字段语义同 ``ReorderTestCaseSchema``，但不含 ``project_id`` 和
    ``source_module_id``（批量接口在父级统一指定）。
    """

    case_id: int = Field(..., description="被移动的用例ID")
    target_module_id: Optional[int] = Field(
        None, description="目标模块ID；None 表示在原 module 内移动"
    )
    before_id: Optional[int] = Field(
        None, description="锚点：被移动 case 放在此 case 之前"
    )
    after_id: Optional[int] = Field(
        None, description="锚点：被移动 case 放在此 case 之后"
    )


class ReorderTestCaseSchema(BaseModel):
    """重排序用例（module 维度, 单 case 移动语义）

    设计原则
    --------
    - 前端只传"被移动 case + 锚点"两个关键 ID，传输量与列表规模无关
    - 服务端基于锚点重新计算目标 module 的整组顺序，
      用单条 ``UPDATE ... CASE`` 表达式一次回写, 避免 N 次 roundtrip
    - 天然支持跨 module 移动（``target_module_id`` 指定新模块即可）

    锚点语义
    --------
    - ``before_id`` 优先：被移动 case 放在此 case 之前
    - ``after_id`` 次之：被移动 case 放在此 case 之后
    - 都为空：被移动 case 移到目标 module 末尾
    """

    project_id: int = Field(..., description="所属项目ID")
    case_id: int = Field(..., description="被移动的用例ID")
    target_module_id: Optional[int] = Field(
        None, description="目标模块ID；None 表示在原 module 内移动"
    )
    before_id: Optional[int] = Field(
        None, description="锚点：被移动 case 放在此 case 之前"
    )
    after_id: Optional[int] = Field(
        None, description="锚点：被移动 case 放在此 case 之后"
    )


class BulkReorderTestCaseSchema(BaseModel):
    """批量重排序用例

    典型场景
    --------
    - **多选拖拽**：一次拖动 N 个连续用例到新位置，每条 item 用同一锚点
    - **跨 module 批量调整**：把若干 case 从 A 模块移到 B 模块指定位置
    - **混合操作**：items 内允许跨 module，顺序应用

    行为
    ----
    - 所有 items 在 **同一事务** 内顺序应用；任一失败整体回滚
    - 越权前置：聚合所有 case_id + 锚点去重后一次性校验, 省去 N 次 SELECT
    - 单条应用的执行逻辑与 ``reorder_test_case`` 完全一致
      （共用 _apply_single_reorder）

    Returns:
        接口返回每条 item 的 affected 行数列表, 便于前端精确定位失败项
    """

    project_id: int = Field(..., description="所属项目ID")
    items: List[ReorderTestCaseItem] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="批量重排序条目（1~500）；同一事务内顺序应用",
    )


class ReorderCaseStep(BaseModel):
    """重排序用例步骤模型"""
    step_ids: List[int] = Field(..., description="步骤ID列表")


class RemoveCaseStep(BaseModel):
    """删除用例步骤模型"""
    stepId: int = Field(..., description="步骤ID")


class AddDefaultCaseStep(BaseModel):
    """添加默认用例步骤模型"""
    caseId: int = Field(..., description="用例ID")


class UpdateTestCaseStep(BaseModel):
    """更新测试用例步骤模型"""
    id: int = Field(..., description="步骤ID")
    action: Optional[str] = Field(None, description="操作步骤")
    expected_result: Optional[str] = Field(None, description="预期结果")
    order: Optional[int] = Field(None, description="排序序号")


class SetCasesCommonSchema(BaseModel):
    """设置多个用例为公共用例模型"""
    case_ids: List[int] = Field(..., description="用例ID列表")
    module_id: int = Field(..., description="模块ID")
    project_id: int = Field(..., description="项目ID")


class UploadPreviewResult(BaseModel):
    """上传预览结果模型"""
    file_md5: Optional[str] = Field(None, description="文件唯一标识")
    total_count: int = Field(..., description="总行数")
    valid_count: int = Field(..., description="有效用例数")
    invalid_count: int = Field(..., description="无效行数")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="具体错误信息")
    preview_data: List[Dict[str, Any]] = Field(default_factory=list, description="预览数据（前10条）")
    file_exists: bool = Field(False, description="文件是否已存在")
    can_commit: bool = Field(
        True,
        description=(
            "是否可提交入库. False 时 Redis 中无预览缓存, 前端必须禁用 commit 按钮, "
            "强制用户修正 Excel 后整批重传."
        ),
    )
    # PR-3 新增: 模板类型. M1=老模板(下载的空白模版)走 on_duplicate 老逻辑,
    # M2=导出模板(有 _meta sheet)走 case_id 同步. 老调用方不感知, 默认 M1.
    template_type: Literal["M1", "M2"] = Field(
        "M1",
        description=(
            "模板类型: M1=老模板(9 列, 无 _meta), M2=导回模板(14 列, 有 _meta sheet). "
            "M1 走 on_duplicate 老逻辑, M2 走 case_id 同步."
        ),
    )
    # PR-3 新增: 警告信息. M2 解析可能产生 (如某行有 case_id 但 DB 查不到对应 case).
    warnings: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="警告信息, 不阻塞 commit, 仅前端提示用",
    )


class UploadCommitSchema(BaseModel):
    """确认入库请求模型"""
    file_md5: str = Field(..., description="文件唯一标识")
    project_id: int = Field(..., description="项目ID")
    module_id: Optional[int] = Field(None, description="模块ID")
    requirement_id: Optional[int] = Field(None, description="需求ID")
    is_common: bool = Field(True, description="是否公共")
    on_duplicate: Literal["skip", "create"] = Field(
        "create",
        description=(
            "相同用例处理. 当 Excel 中的用例与导入位置已有的用例"
            "(project_id, module_id, case_name) 三元组完全一致时:"
            "- skip:    跳过该用例, 不写入 (计入 skipped_count)"
            "- create:  仍然写入, 允许同名同分组的多条用例并存 (默认)"
        ),
    )


class UploadCancelSchema(BaseModel):
    """取消上传请求模型"""
    file_md5: str = Field(..., description="文件唯一标识")


# ============================================================
# PR-3 Step 3 新增 (见 PLAN.md 4 步实施段)
# ============================================================

class ImportCommitSchema(BaseModel):
    """
    PR-3 Step 3: M2 导回 commit 请求模型.

    跟老 UploadCommitSchema 的区别:
    - 没有 on_duplicate 字段 (M2 强制按 case_id 同步, 名字冲突不跳过)
    - 没有 is_common 字段 (M2 导回时通过 _meta 决定)
    - module_id 改可选, 因为 M2 导回时 scope_type/scope_id 在 _meta 里,
      库场景 module_id 就从 _meta 拿 (没传就用 _meta 里的 scope_id 当 module)
    - requirement_id 仍保留, 但 M2 库场景不会传
    """
    file_md5: str = Field(..., description="preview 阶段返的 MD5 指纹")
    project_id: int = Field(..., description="目标项目 ID")
    module_id: Optional[int] = Field(None, description="模块ID (可选, new case 默认 module 兜底)")


class ImportCancelSchema(BaseModel):
    """PR-3 Step 3: M2 导回 cancel 请求模型 (跟老 UploadCancelSchema 一致)."""
    file_md5: str = Field(..., description="文件唯一标识")
