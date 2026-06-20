# 本次 (含本会话) Schema 同步清单

> 用途: 换机换库时, 对照此文档跑手工 DDL
> 来源: 自 `41f4879` 起到 `9bd30f6` 共 23 个 commit 的 model/mapper diff
> 风险等级: **中** (有 2 张表改列类型, 需在低峰期跑 + 全量备份)

---

## 1. 真正需要 DDL 的字段 (按表归类)

### 1.1 `play_task_result.rate_number`: `INT` → `FLOAT`

- **原因**: BUG-P-1-3, MySQL 静默截断 85.5% → 85%
- **影响**: 1 张表, 1 个字段, INT → FLOAT 字节数相同 (4 字节), 自动转换, **不需要数据迁移**
- **SQL**:
  ```sql
  ALTER TABLE play_task_result
      MODIFY COLUMN rate_number FLOAT DEFAULT 0
      COMMENT '通过率';
  ```
- **回滚**:
  ```sql
  ALTER TABLE play_task_result MODIFY COLUMN rate_number INT DEFAULT 0 COMMENT '通过率';
  ```

### 1.2 `interface_case_step_content.content_type`: `INT` → `VARCHAR(20)` (enum NAME)

- **原因**: BUG-M5, 改用 Enum 类型, 避免重排枚举值时旧数据全错
- **影响**: 1 张表, 1 个字段, int value → enum NAME, **需要数据迁移**
- **enum 实际值**:
  ```
  STEP_API=1, STEP_API_GROUP=2, STEP_API_CONDITION=3,
  STEP_API_SCRIPT=4, STEP_API_DB=5, STEP_API_WAIT=6,
  STEP_API_ASSERT=8, STEP_LOOP=9
  (注意 7 是历史空缺, 不能用 BETWEEN, 必须 WHERE = 1/2/3/...)
  ```
- **SQL**:
  ```sql
  ALTER TABLE interface_case_step_content
      MODIFY COLUMN content_type VARCHAR(20) COMMENT '步骤类型 (enum NAME)';

  UPDATE interface_case_step_content SET content_type = 'STEP_API'          WHERE content_type = '1';
  UPDATE interface_case_step_content SET content_type = 'STEP_API_GROUP'    WHERE content_type = '2';
  UPDATE interface_case_step_content SET content_type = 'STEP_API_CONDITION' WHERE content_type = '3';
  UPDATE interface_case_step_content SET content_type = 'STEP_API_SCRIPT'   WHERE content_type = '4';
  UPDATE interface_case_step_content SET content_type = 'STEP_API_DB'       WHERE content_type = '5';
  UPDATE interface_case_step_content SET content_type = 'STEP_API_WAIT'     WHERE content_type = '6';
  UPDATE interface_case_step_content SET content_type = 'STEP_API_ASSERT'   WHERE content_type = '8';
  UPDATE interface_case_step_content SET content_type = 'STEP_LOOP'         WHERE content_type = '9';
  -- 验证
  SELECT content_type, COUNT(*) AS leftover FROM interface_case_step_content
      WHERE content_type REGEXP '^[0-9]+$' GROUP BY content_type;
  -- 期望: 0 行
  ```

### 1.3 `interface_case_content_result.content_type`: `INT` → `VARCHAR(20)` (enum NAME)

- **原因**: BUG-M5, 同 1.2
- **SQL**: 同 1.2, 表名换 `interface_case_content_result`

### 1.4 `interface_case_content_result.status`: `String(20)` → `String(20)` (内容替换)

- **原因**: BUG-M9, 写库走 StepStatusEnum, 只接受 SUCCESS/FAIL/PENDING
- **影响**: 字段类型不变, 仅数据侧值替换
- **SQL** (可选, 仅当历史有非三选一脏数据时):
  ```sql
  -- 脏数据检查
  SELECT status, COUNT(*) AS n FROM interface_case_content_result
      WHERE status NOT IN ('SUCCESS', 'FAIL', 'PENDING') GROUP BY status;
  -- 期望: 0 行; 如有, 跑下方兜底
  UPDATE interface_case_content_result
      SET status = 'PENDING'
      WHERE status NOT IN ('SUCCESS', 'FAIL', 'PENDING');
  ```
- **schema DDL**: 无, `native_enum=False` 走 VARCHAR(20), 已存在 String(20) 字段自动兼容

### 1.5 `interface_case_result.*`: VARCHAR 扩长

- **原因**: BUG-M2 (name 20→64, desc 50→255), BUG-M11 (uid 20→50)
- **SQL**:
  ```sql
  ALTER TABLE interface_case_result
      MODIFY COLUMN interface_case_name VARCHAR(64)  COMMENT '用例名称',
      MODIFY COLUMN interface_case_desc VARCHAR(255) COMMENT '用例描述',
      MODIFY COLUMN interface_case_uid  VARCHAR(50)  COMMENT '用例Uid';
  ```

### 1.6 `interface_result.interface_uid`: VARCHAR(20) → VARCHAR(50)

- **原因**: BUG-M11
- **SQL**:
  ```sql
  ALTER TABLE interface_result MODIFY COLUMN interface_uid VARCHAR(50) COMMENT '用例Uid';
  ```

### 1.7 `interface_task_result.task_uid`: VARCHAR(10) → VARCHAR(50)

- **原因**: BUG-M11
- **SQL**:
  ```sql
  ALTER TABLE interface_task_result
      MODIFY COLUMN task_uid VARCHAR(50) NOT NULL COMMENT 'task索引';
  ```

---

## 2. 已记录在 `docs/MANUAL_MIGRATION.sql` 的脚本

完整脚本位置: `docs/MANUAL_MIGRATION.sql` (204 行, 包含上述 1.1-1.7 + 验证回查 + 回滚 SQL)

---

## 3. 不需要 DDL 的变更 (Python 代码层, 已部署生效)

| BUG | 改动 | 是否需要 DDL |
|---|---|---|
| P-1-1 | 32 处 `raise e` → `raise` (保留 traceback) | 否 |
| P-1-2 | `ui_case_Id` 错属性名 + 加 `ui_case_id` property 兼容 | 否 (DB 列名保留 `ui_case_Id`, 1-2 release 过渡后彻底改) |
| P-1-3 | `rate_number` INT → FLOAT | **是** (见 1.1) |
| P-1-4 | `write_result(SUCCESS: bool)` → `success` 命名 | 否 |
| P-1-5 | `__repr__` 末尾 `> />` → `/>` | 否 |
| P-1-6 | `use_time` 黑洞重算 | 否 |
| P-1-7 | `__clean` / `__init_page` → `_clean` / `_init_page` | 否 (单下划线, 仍 private) |
| P-1-8 | `init_case_variables` 失败只 log 不 raise | 否 |
| F1-F12 | 各种 BUG 修复 | 否 (代码层) |
| E1-E11 | 各种 BUG 修复 | 否 (代码层) |
| M1-M11 | 各种 BUG 修复 | 大部分否 (除 M2/M5/M9/M11) |
| V1-V6 | 各种 BUG 修复 | 否 |
| S1-S4 | 各种 BUG 修复 | 否 |
| D1-D10 | 各种 BUG 修复 | 否 |
| T1-T2 | 任务级执行 | 否 |
| P-R1 ~ P-R5 | UI P0 | 否 |
| P-2-1 ~ P-2-3 | UI P2 | 否 |
| P-3-1 | 覆盖率测试 | 否 |
| P-4-1 | SocketSender 污染 | 否 |
| OBS-1 ~ OBS-6 | observability (trace_id, log redaction) | 否 (无新字段) |

---

## 4. 跑迁移的顺序建议

1. **全量备份** (mysqldump 6 张表):
   ```bash
   mysqldump -h $HOST -u $USER -p$PASS case_auto_hub \
     play_task_result \
     interface_case_step_content \
     interface_case_content_result \
     interface_case_result \
     interface_result \
     interface_task_result \
     > /backup/case_auto_hub_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **扩 VARCHAR** (1.5/1.6/1.7, 无 DML 风险, 先跑):
   - 这些只是改长度, 已存在的短值不受影响, 索引 / FK / 视图都兼容

3. **content_type int → enum NAME** (1.2/1.3, 风险最大):
   - 先 UPDATE 翻译 (8 个 case WHEN)
   - 再 ALTER 改列类型
   - 验证: `SELECT ... WHERE content_type REGEXP '^[0-9]+$'` 应返 0 行

4. **status 数据兜底** (1.4, 可选):
   - sanity check 现有 status 是不是只在 {'SUCCESS','FAIL','PENDING'}
   - 异常值 UPDATE 成 PENDING

5. **play_task_result.rate_number INT → FLOAT** (1.1):
   - 字节数相同, 自动转换, 无 DML 风险, 放最后跑

6. **部署应用代码** (后端先发, DB 已就绪)
7. **前端** (无 schema 依赖, 可独立发)

---

## 5. 验证回查 (一键全跑)

```sql
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND (
    (TABLE_NAME = 'play_task_result' AND COLUMN_NAME = 'rate_number')
    OR (TABLE_NAME = 'interface_case_step_content' AND COLUMN_NAME = 'content_type')
    OR (TABLE_NAME = 'interface_case_content_result' AND COLUMN_NAME = 'content_type')
    OR (TABLE_NAME = 'interface_case_content_result' AND COLUMN_NAME = 'status')
    OR (TABLE_NAME = 'interface_case_result' AND COLUMN_NAME IN ('interface_case_name','interface_case_desc','interface_case_uid'))
    OR (TABLE_NAME = 'interface_result' AND COLUMN_NAME = 'interface_uid')
    OR (TABLE_NAME = 'interface_task_result' AND COLUMN_NAME = 'task_uid')
  )
ORDER BY TABLE_NAME, COLUMN_NAME;
```

期望:
- `play_task_result.rate_number` = `float`
- `interface_case_step_content.content_type` = `varchar` (length 20)
- `interface_case_content_result.content_type` = `varchar` (length 20)
- `interface_case_content_result.status` = `varchar` (length 20)
- `interface_case_result.interface_case_name` = `varchar` (length 64)
- `interface_case_result.interface_case_desc` = `varchar` (length 255)
- `interface_case_result.interface_case_uid` = `varchar` (length 50)
- `interface_result.interface_uid` = `varchar` (length 50)
- `interface_task_result.task_uid` = `varchar` (length 50)
