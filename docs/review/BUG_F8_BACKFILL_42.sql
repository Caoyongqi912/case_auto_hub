-- ============================================================
-- BUG-F8 历史数据回填: case_result=42 修复前被丢的 content_result
-- ============================================================
-- 背景: F8 修复前 (D1 修复不闭环), 8 个 step_content_*.py 仍
--      用模块级单例 result_writer, STEP_API content_result 写
--      进单例 cache 永远不被 flush, 进程退出后丢失。
--      case_result=42 是这次 bug 的直接受害者, 表现为:
--      /api/interfaceResult/queryStepResult?case_result_id=42
--      返回空, 但 interface_result 表有 id=133 (content_result_id=NULL)。
--
-- 目标: 依据 interface_result.id=133 + interface_case_content_association
--       重建最低限度的失败记录, 让 API 能拿到 step_result 数据。
--
-- 注意: 这是补救措施, 不是修复。修复见代码 commit (F8)。
--       用完此 SQL 即可, 不需要重复执行 (id=154 已存在则报错)。
-- ============================================================

START TRANSACTION;

-- 1. 父表: 拿 case_result 字段 + step 关联填充 content_result
INSERT INTO interface_case_content_result (
    case_result_id, task_result_id, content_id, content_name,
    content_desc, content_step, content_type, result, status,
    start_time, use_time, create_time, update_time,
    creator, creatorName, updater, updaterName
)
SELECT
    42 AS case_result_id,
    NULL AS task_result_id,
    assoc.interface_case_content_id AS content_id,
    'randomName' AS content_name,
    NULL AS content_desc,
    assoc.step_order AS content_step,
    'STEP_API' AS content_type,
    0 AS result,
    'FAIL' AS status,
    cr.start_time AS start_time,
    cr.use_time AS use_time,
    NOW() AS create_time,
    NOW() AS update_time,
    cr.creator,
    cr.creatorName,
    cr.creator,
    cr.creatorName
FROM interface_case_result cr
JOIN interface_case_content_association assoc
  ON assoc.interface_case_id = cr.interface_case_id
WHERE cr.id = 42
  AND assoc.interface_case_content_id IN (
    SELECT id FROM interface_case_step_content
    WHERE content_type = 'STEP_API'
  );

-- 2. 子表 (Joined Table Inheritance): 把 interface_result 关联到刚插的 content_result
INSERT INTO interface_case_content_result_api (
    result_id, interface_result_id
)
SELECT
    cr_parent.id AS result_id,
    133 AS interface_result_id
FROM interface_case_content_result cr_parent
WHERE cr_parent.case_result_id = 42
  AND cr_parent.content_type = 'STEP_API'
LIMIT 1;

-- 3. 验证 (回填完应该 1 行)
-- SELECT * FROM interface_case_content_result WHERE case_result_id = 42;

COMMIT;
