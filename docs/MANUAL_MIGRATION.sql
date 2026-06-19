-- ============================================================
-- case_auto_hub P0 修复 — 手工 SQL 迁移脚本
-- 日期: 2026-06-19
-- 对应 commit: c128881, 3f9d6ab
-- 说明: 项目未引入 alembic,所有 DDL 变更需要 DBA 手工执行
-- 风险等级: 低 (只是扩长 VARCHAR,无 NOT NULL / 索引 / 外键变更)
-- 备份: 建议先对 3 张表做 mysqldump
-- ============================================================

-- ---------- 前置: 备份 ----------
-- mysqldump -h $HOST -u $USER -p$PASS case_auto_hub \
--   interface_case_result interface_result interface_task_result \
--   > /backup/case_auto_hub_p0_$(date +%Y%m%d).sql

-- ============================================================
-- 变更 1: interface_case_result
--   interface_case_name  VARCHAR(20)  -> VARCHAR(64)   (BUG-M2)
--   interface_case_desc  VARCHAR(50)  -> VARCHAR(255)  (BUG-M2)
--   interface_case_uid   VARCHAR(20)  -> VARCHAR(50)   (BUG-M11)
-- ============================================================
ALTER TABLE interface_case_result
    MODIFY COLUMN interface_case_name VARCHAR(64)  COMMENT '用例名称',
    MODIFY COLUMN interface_case_desc VARCHAR(255) COMMENT '用例描述',
    MODIFY COLUMN interface_case_uid  VARCHAR(50)  COMMENT '用例Uid';

-- ============================================================
-- 变更 2: interface_result
--   interface_uid  VARCHAR(20)  -> VARCHAR(50)  (BUG-M11)
-- ============================================================
ALTER TABLE interface_result
    MODIFY COLUMN interface_uid VARCHAR(50) COMMENT '用例Uid';

-- ============================================================
-- 变更 3: interface_task_result
--   task_uid  VARCHAR(10)  -> VARCHAR(50)  (BUG-M11)
-- ============================================================
ALTER TABLE interface_task_result
    MODIFY COLUMN task_uid VARCHAR(50) NOT NULL COMMENT 'task索引';

-- ============================================================
-- 验证回查 (期望 0 行)
-- ============================================================
-- SELECT TABLE_NAME, COLUMN_NAME, CHARACTER_MAXIMUM_LENGTH
-- FROM information_schema.COLUMNS
-- WHERE TABLE_SCHEMA = DATABASE()
--   AND (
--     (TABLE_NAME = 'interface_case_result' AND COLUMN_NAME IN ('interface_case_name','interface_case_desc','interface_case_uid'))
--     OR (TABLE_NAME = 'interface_result' AND COLUMN_NAME = 'interface_uid')
--     OR (TABLE_NAME = 'interface_task_result' AND COLUMN_NAME = 'task_uid')
--   )
--   AND CHARACTER_MAXIMUM_LENGTH < 50;
