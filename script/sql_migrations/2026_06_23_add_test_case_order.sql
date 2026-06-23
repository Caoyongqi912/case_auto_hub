-- ============================================================
-- 2026-06-23: 为 test_case 表加 order 字段（用例库 module 维度拖拽排序）
-- ============================================================
-- 背景:
--   case_auto_hub 用 BaseModel.metadata.create_all(checkfirst=True) 自动建表,
--   但 create_all 不会改已存在表的列结构, 已有 test_case 表需要手动 ALTER.
--
-- 字段:
--   order INT NOT NULL DEFAULT 0
--     - 用例在所属 module 内的排序序号
--     - 默认 0 让历史数据 / 新增用例自然落到末尾
--     - 前端 DragSortTable 拖拽后由 POST /hub/cases/reorder 维护
--
-- 索引:
--   idx_test_case_order (order)
--     - page 接口默认 sort: { order: ascend, id: ascend } 走此索引
--     - 历史全量数据补完后, 列表首屏排序性能稳定
--
-- 兼容性:
--   - 字段 NOT NULL DEFAULT 0: 已有行自动回填 0, 无需 UPDATE
--   - 加列 + 加索引两步走, 中间失败可重入 (idempotent)
--   - 失败回滚: ALTER TABLE DROP COLUMN `order` / DROP INDEX idx_test_case_order
-- ============================================================

ALTER TABLE test_case
    ADD COLUMN `order` INT NOT NULL DEFAULT 0 COMMENT '排序序号';

CREATE INDEX idx_test_case_order ON test_case (`order`);
