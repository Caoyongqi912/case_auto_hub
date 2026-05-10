-- 性能优化索引创建脚本
-- 为 TestCase 表添加关键索引

-- 1. 为 case_name 添加索引（支持模糊查询）
CREATE INDEX IF NOT EXISTS idx_test_case_name ON test_case(case_name);

-- 2. 为 case_tag 添加索引（支持标签过滤）
CREATE INDEX IF NOT EXISTS idx_test_case_tag ON test_case(case_tag);

-- 3. 为 module_id 添加索引（支持模块查询）
CREATE INDEX IF NOT EXISTS idx_test_case_module_id ON test_case(module_id);

-- 4. 为 project_id 添加索引（支持项目查询）
CREATE INDEX IF NOT EXISTS idx_test_case_project_id ON test_case(project_id);

-- 5. 复合索引：module_id + project_id（支持联合查询）
CREATE INDEX IF NOT EXISTS idx_test_case_module_project ON test_case(module_id, project_id);

-- 6. 为 is_common 添加索引（支持公共用例查询）
CREATE INDEX IF NOT EXISTS idx_test_case_is_common ON test_case(is_common);

-- 7. 为 RequirementCaseAssociation 添加额外的性能索引
-- 注意：requirement_id 和 order 的复合索引已存在 (idx_req_case_order)

-- 8. 为 case_status 添加索引（支持状态过滤）
CREATE INDEX IF NOT EXISTS idx_requirement_case_status ON requirement_case_association(case_status);

-- 9. 为 case_type 添加索引（支持类型过滤）
CREATE INDEX IF NOT EXISTS idx_requirement_case_type ON requirement_case_association(case_type);

-- 10. 为 case_level 添加索引（支持等级过滤）
CREATE INDEX IF NOT EXISTS idx_requirement_case_level ON requirement_case_association(case_level);

-- 11. 为 is_review 添加索引（支持审核状态过滤）
CREATE INDEX IF NOT EXISTS idx_requirement_case_is_review ON requirement_case_association(is_review);

-- 查看索引创建情况
SHOW INDEX FROM test_case;
SHOW INDEX FROM requirement_case_association;

-- 分析表以优化查询计划
ANALYZE TABLE test_case;
ANALYZE TABLE requirement_case_association;
