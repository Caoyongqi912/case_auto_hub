#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/7/3
# @Author : cyq
# @File : __init__.py
# @Software: PyCharm
# @Desc: play模块导出

from .playCaseSchema import (
    PlayCaseBasicSchema,
    EditPlayCaseBasicSchema,
    GetPlayCaseByCaseId,
    PagePlayCaseSchema,
    ReOrderPlayStepSchema,
    PlayCaseChoiceStepSchema,
    PagePlayCaseResultSchema,
    InsertPlayCaseVariableSchema,
    EditPlayCaseVariableSchema,
    GetPlayCaseVariableSchema,
    PagePlayCaseVariableSchema,
    PlayCaseChoiceGroupStepSchema
)

from .playStepSchema import (
    InsertPlayStepSchema,
    UpdatePlayStepSchema,
    PagePlayStepSchema,
    CopyPlayStepSchema,
    AssociationStepApiSchema,
    InsertPlayConditionStepSchema,
    ReorderPlayConditionStepsSchema,
    CopyPlayCaseStepContentSchema
)

from .playConfigSchema import (
    AddPlayMethodSchema,
    EditPlayMethodSchema,
    GetPlayMethodSchema,
    PagePlayMethodSchema
)

from .playStepGroupSchema import (
    InsertPlayStepGroupSchema,
    PagePlayStepGroupSchema,
    InsertPlaySubStepSchema,
    GetPlaySubStepByIdSchema,
    UpdatePlayStepGroupSchema,
    RemovePlayStepGroupSchema,
    ReOrderPlaySubStepsSchema
)

from .playTaskSchema import *