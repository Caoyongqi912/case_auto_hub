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

-- ============================================================
-- M5 追加: content_type 改 VARCHAR(20), int -> enum NAME
-- 日期: 2026-06-19
-- 对应 commit: <本轮 M5>
-- 风险等级: 中 (改列类型 + UPDATE 全表, 需在低峰期跑)
-- 备份: 必须先 mysqldump 备份 interface_case_step_content +
--       interface_case_content_result 两张基类表
-- ============================================================

-- ---------- 前置: 备份 ----------
-- mysqldump -h $HOST -u $USER -p$PASS case_auto_hub \
--   interface_case_step_content interface_case_content_result \
--   > /backup/case_auto_hub_m5_$(date +%Y%m%d).sql

-- ---------- 步骤 1: 改列类型到 VARCHAR(20) ----------
ALTER TABLE interface_case_step_content
    MODIFY COLUMN content_type VARCHAR(20) COMMENT '步骤类型 (enum NAME)';

ALTER TABLE interface_case_content_result
    MODIFY COLUMN content_type VARCHAR(20) COMMENT '步骤类型 (enum NAME)';

-- ---------- 步骤 2: int -> name 数据迁移 ----------
-- CaseStepContentType 当前值:
--   STEP_API = 1, STEP_API_GROUP = 2, STEP_API_CONDITION = 3,
--   STEP_API_SCRIPT = 4, STEP_API_DB = 5, STEP_API_WAIT = 6,
--   STEP_API_ASSERT = 8, STEP_LOOP = 9
-- (注意 7 是历史空缺, 不能用 BETWEEN)

UPDATE interface_case_step_content SET content_type = 'STEP_API'          WHERE content_type = '1';
UPDATE interface_case_step_content SET content_type = 'STEP_API_GROUP'    WHERE content_type = '2';
UPDATE interface_case_step_content SET content_type = 'STEP_API_CONDITION' WHERE content_type = '3';
UPDATE interface_case_step_content SET content_type = 'STEP_API_SCRIPT'   WHERE content_type = '4';
UPDATE interface_case_step_content SET content_type = 'STEP_API_DB'       WHERE content_type = '5';
UPDATE interface_case_step_content SET content_type = 'STEP_API_WAIT'     WHERE content_type = '6';
UPDATE interface_case_step_content SET content_type = 'STEP_API_ASSERT'   WHERE content_type = '8';
UPDATE interface_case_step_content SET content_type = 'STEP_LOOP'         WHERE content_type = '9';

UPDATE interface_case_content_result SET content_type = 'STEP_API'          WHERE content_type = '1';
UPDATE interface_case_content_result SET content_type = 'STEP_API_GROUP'    WHERE content_type = '2';
UPDATE interface_case_content_result SET content_type = 'STEP_API_CONDITION' WHERE content_type = '3';
UPDATE interface_case_content_result SET content_type = 'STEP_API_SCRIPT'   WHERE content_type = '4';
UPDATE interface_case_content_result SET content_type = 'STEP_API_DB'       WHERE content_type = '5';
UPDATE interface_case_content_result SET content_type = 'STEP_API_WAIT'     WHERE content_type = '6';
UPDATE interface_case_content_result SET content_type = 'STEP_API_ASSERT'   WHERE content_type = '8';
UPDATE interface_case_content_result SET content_type = 'STEP_LOOP'         WHERE content_type = '9';

-- ---------- 步骤 3: 验证 (任意一个 int 都不应还存在) ----------
SELECT content_type, COUNT(*) AS leftover FROM interface_case_step_content
    WHERE content_type REGEXP '^[0-9]+$' GROUP BY content_type;
SELECT content_type, COUNT(*) AS leftover FROM interface_case_content_result
    WHERE content_type REGEXP '^[0-9]+$' GROUP BY content_type;
-- 期望: 0 行返回 (如果还有, 表示 enum 整数值和 CaseStepContentType 对不上, 检查 enums/CaseEnum.py)

-- ---------- 回滚 (如需要) ----------
-- ALTER TABLE interface_case_step_content
--     MODIFY COLUMN content_type INT COMMENT '步骤类型';
-- UPDATE interface_case_step_content SET content_type = 1 WHERE content_type = 'STEP_API';
-- UPDATE interface_case_step_content SET content_type = 2 WHERE content_type = 'STEP_API_GROUP';
-- UPDATE interface_case_step_content SET content_type = 3 WHERE content_type = 'STEP_API_CONDITION';
-- UPDATE interface_case_step_content SET content_type = 4 WHERE content_type = 'STEP_API_SCRIPT';
-- UPDATE interface_case_step_content SET content_type = 5 WHERE content_type = 'STEP_API_DB';
-- UPDATE interface_case_step_content SET content_type = 6 WHERE content_type = 'STEP_API_WAIT';
-- UPDATE interface_case_step_content SET content_type = 8 WHERE content_type = 'STEP_API_ASSERT';
-- UPDATE interface_case_step_content SET content_type = 9 WHERE content_type = 'STEP_LOOP';
-- (对 interface_case_content_result 同样)


-- ============================================================================
-- BUG-M9: interface_case_content_result.status 从 String(20) 改 Enum
--         (StepStatusEnum, native_enum=False, length=20)
-- ============================================================================
-- 背景:
--   * 原 status 字段是 String(20), 8 个 step_content 文件写 "SUCCESS"/"FAIL"
--     字面量, 写错字符串 (e.g. "success"/"OK"/"DONE") 不会报错, 要等前端 /
--     DB 查询才发现。
--   * M9 修: 字段改 Enum(StepStatusEnum, native_enum=False, length=20),
--     写库只接受 "SUCCESS"/"FAIL"/"PENDING", 跟 M5 content_type 同模式。
--   * 历史 PENDING 字符串 (旧 default="PENDING") 仍合法, 已纳入 enum。
--
-- 兼容分析:
--   * String(20) → VARCHAR(20): 长度一致, 不需要改 schema 类型, SQLAlchemy
--     用 native_enum=False 走 VARCHAR, 数据库侧无感。
--   * 数据侧: 现有 "SUCCESS"/"FAIL"/"PENDING" 三个合法值, 都不用改;
--     如果历史有非三选一脏数据 (理论上没, 但先 sanity check), 需要 UPDATE 成
--     PENDING 兜底。

-- ---------- 步骤 1: 脏数据 sanity check ----------
SELECT status, COUNT(*) AS n FROM interface_case_content_result
    WHERE status NOT IN ('SUCCESS', 'FAIL', 'PENDING')
    GROUP BY status;
-- 期望: 0 行返回
-- 如果有, 走步骤 1.5 兜底

-- ---------- 步骤 1.5 (可选, 仅当步骤 1 有返回值时执行) ----------
-- UPDATE interface_case_content_result
--     SET status = 'PENDING'
--     WHERE status NOT IN ('SUCCESS', 'FAIL', 'PENDING');

-- ---------- 步骤 2: 应用层就绪 (代码已部署) ----------
-- 无需 schema DDL: native_enum=False 走 VARCHAR(20), 已存在的 String(20)
-- 字段可直接被 Enum(StepStatusEnum, native_enum=False, length=20) 读写。
-- ORM 层 INSERT / SELECT 完全兼容。
-- (若以后想收紧成 native ENUM, 见步骤 3)

-- ---------- 步骤 3 (可选, 改 MySQL 原生 ENUM 类型) ----------
-- ALTER TABLE interface_case_content_result
--     MODIFY COLUMN status ENUM('SUCCESS','FAIL','PENDING') NOT NULL DEFAULT 'PENDING'
--     COMMENT '执行状态';
-- 注意: 这一步会让 SQLAlchemy 端 native_enum=True 才能配合, 模型还得再改,
-- 现阶段没强需求, 跳过。

-- ---------- 回滚 (如需要) ----------
-- 应用层回滚:
--   * git revert M9 commit
--   * 字段类型自动回到 String(20), "SUCCESS"/"FAIL"/"PENDING" 仍合法
--   * 老 default="PENDING" 也回得来
-- 数据库侧无需动作。
