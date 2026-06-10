-- Migration: 给 plan_module 表添加 source_module_id 字段
-- Date: 2026-06-10
-- Desc: 建立 PlanModule 与 Module（用例库分组）的持久化关联，支持双向同步优化

-- 1. 新增字段
ALTER TABLE plan_module
    ADD COLUMN source_module_id INT NULL
    COMMENT '来源用例库模块ID（从用例库复制/关联时记录）'
    AFTER `order`;

-- 2. 添加外键约束（可选，生产环境建议加）
-- ALTER TABLE plan_module
--     ADD CONSTRAINT fk_plan_module_source
--     FOREIGN KEY (source_module_id) REFERENCES module(id)
--     ON DELETE SET NULL;

-- 3. 添加索引（加速按 source_module_id 查找）
CREATE INDEX idx_source_module_id ON plan_module(source_module_id);

-- 注意：
-- - 现有数据的 source_module_id 保持 NULL（留空 + 懒加载回填策略）
-- - 正向复制逻辑（_resolve_source_to_plan_module_map）会在新建 PlanModule 时自动写入该字段
-- - 反向查找逻辑（_resolve_plan_module_to_library_module）会在首次命中时异步回填该字段
-- - 手动创建的分组 source_module_id 始终为 NULL
