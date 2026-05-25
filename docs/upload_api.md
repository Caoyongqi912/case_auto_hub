# 用例批量上传接口文档

## 接口地址

基础路径: `/hub/cases`

---

## 完整流程图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        用例批量上传流程                              │
└─────────────────────────────────────────────────────────────────────┘

  [Step 1]                    [Step 2]                     [Step 3]
  上传预览                    确认入库                     取消上传

┌──────────┐              ┌──────────┐              ┌──────────┐
│  POST    │              │  POST    │              │  POST    │
│  /upload │ ───────────▶ │ /commit  │              │ /cancel  │
└──────────┘              └──────────┘              └──────────┘
     │                        │                          │
     ▼                        ▼                          ▼
 上传文件              传入 file_md5              传入 file_md5
 解析并校验              选择入库项                 清理缓存
 返回 md5               执行入库                   释放内存
```

---

## 接口详情

### Step 1: 上传预览

**接口地址:** `POST /hub/cases/upload`

**请求方式:** `multipart/form-data`

**请求参数:**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| file | File | 是 | Excel 文件 (.xlsx/.xls) |

**请求示例:**

```bash
curl -X POST "http://localhost:8000/hub/cases/upload" \
  -H "Authorization: Bearer <token>" \
  -F "file=@test_cases.xlsx"
```

**成功响应:**

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "file_md5": "a1b2c3d4e5f6789012345678901234ab",
    "total_count": 50,
    "valid_count": 48,
    "invalid_count": 2,
    "errors": [
      {
        "row": 5,
        "errors": [
          {
            "field": "case_tag",
            "message": "用例标签不能为空"
          }
        ]
      },
      {
        "row": 12,
        "errors": [
          {
            "field": "case_name",
            "message": "用例名称不能为空"
          }
        ]
      }
    ]
  }
}
```

**错误响应:**

```json
{
  "code": 500,
  "msg": "导入失败: 第5行: 用例标签不能为空",
  "data": null
}
```

**响应字段说明:**

| 字段 | 类型 | 说明 |
|------|------|------|
| file_md5 | string | 文件唯一标识，用于后续确认入库 |
| total_count | int | Excel 总行数 |
| valid_count | int | 有效用例数 |
| invalid_count | int | 无效行数 |
| errors | array | 错误详情列表 |
| errors[].row | int | 错误所在行号 |
| errors[].errors | array | 该行具体错误 |
| errors[].errors[].field | string | 错误字段名 |
| errors[].errors[].message | string | 错误信息 |

---

### Step 2: 确认入库

**接口地址:** `POST /hub/cases/upload/commit`

**请求方式:** `application/json`

**请求参数:**

```json
{
  "file_md5": "a1b2c3d4e5f6789012345678901234ab",
  "valid_case_ids": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
  "project_id": 1,
  "module_id": 2,
  "requirement_id": 10,
  "is_common": true
}
```

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| file_md5 | string | 是 | Step1 返回的文件唯一标识 |
| valid_case_ids | array[int] | 是 | 要入库的用例索引列表 (从0开始) |
| project_id | int | 是 | 项目ID |
| module_id | int | 是 | 模块ID |
| requirement_id | int | 否 | 需求ID |
| is_common | bool | 否 | 是否公共用例 (默认 true) |

**请求示例:**

```bash
curl -X POST "http://localhost:8000/hub/cases/upload/commit" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "file_md5": "a1b2c3d4e5f6789012345678901234ab",
    "valid_case_ids": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    "project_id": 1,
    "module_id": 2,
    "requirement_id": 10,
    "is_common": true
  }'
```

**成功响应:**

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "imported_count": 10
  }
}
```

**错误响应:**

```json
{
  "code": 500,
  "msg": "预览数据已过期，请重新上传文件",
  "data": null
}
```

或

```json
{
  "code": 500,
  "msg": "该文件已提交过，不能重复提交",
  "data": null
}
```

---

### Step 3: 取消上传

**接口地址:** `POST /hub/cases/upload/cancel`

**请求方式:** `application/json`

**请求参数:**

```json
{
  "file_md5": "a1b2c3d4e5f6789012345678901234ab"
}
```

**请求示例:**

```bash
curl -X POST "http://localhost:8000/hub/cases/upload/cancel" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "file_md5": "a1b2c3d4e5f6789012345678901234ab"
  }'
```

**响应:**

```json
{
  "code": 200,
  "msg": "success",
  "data": null
}
```

---

## 重要说明

### 1. 缓存有效期
- `file_md5` 对应的预览数据有效期为 **30 分钟**
- 过期后需重新上传文件

### 2. 幂等控制
- 同一 `file_md5` 只能提交一次
- 重复提交会返回错误

### 3. 索引规则
- `valid_case_ids` 使用 **0-based 索引** (0, 1, 2...)
- 索引对应 Step 1 响应中有效用例的顺序

### 4. 错误处理
- 预览阶段的错误不影响入库
- 用户可选择跳过错误行，只入库有效用例

---

## 前端调用示例

### Vue3 + TypeScript

```typescript
// api/case.ts
import request from '@/utils/request'

// Step 1: 上传预览
export async function uploadPreview(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/hub/cases/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// Step 2: 确认入库
export async function commitImport(data: {
  file_md5: string
  valid_case_ids: number[]
  project_id: number
  module_id: number
  requirement_id?: number
  is_common?: boolean
}) {
  return request.post('/hub/cases/upload/commit', data)
}

// Step 3: 取消上传
export async function cancelImport(file_md5: string) {
  return request.post('/hub/cases/upload/cancel', { file_md5 })
}
```

```typescript
// views/CaseImport.vue
import { uploadPreview, commitImport, cancelImport } from '@/api/case'

async function handleImport(file: File) {
  try {
    // Step 1: 上传预览
    const previewRes = await uploadPreview(file)

    if (previewRes.data.valid_count === 0) {
      ElMessage.error('没有有效用例可导入')
      return
    }

    // 展示预览结果给用户
    showPreviewDialog({
      validCount: previewRes.data.valid_count,
      errors: previewRes.data.errors,
      onConfirm: () => doCommit(previewRes.data.file_md5, previewRes.data.valid_count),
      onCancel: () => cancelImport(previewRes.data.file_md5)
    })

  } catch (error) {
    ElMessage.error('上传失败')
  }
}

async function doCommit(file_md5: string, totalCount: number) {
  // 全部入库
  const ids = Array.from({ length: totalCount }, (_, i) => i)

  const commitRes = await commitImport({
    file_md5,
    valid_case_ids: ids,
    project_id: 1,
    module_id: 2
  })

  ElMessage.success(`成功导入 ${commitRes.data.imported_count} 条用例`)
}
```

---

## Excel 模板格式

### 字段说明

| 列顺序 | 字段名 | 必填 | 说明 | 示例 |
|--------|--------|------|------|------|
| 1 | case_name | 是 | 用例名称 | 登录功能测试 |
| 2 | module | 否 | 模块 | 登录模块 |
| 3 | case_status | 否 | 用例状态 | 待评审 |
| 4 | set_up | 否 | 前置条件 | 已注册用户 |
| 5 | action | 否 | 操作步骤 | 输入账号密码 |
| 6 | expected_result | 否 | 预期结果 | 登录成功 |
| 7 | case_tag | 是 | 用例标签 | 正向用例 |
| 8 | case_level | 否 | 用例等级 | P1/P2/P3 |
| 9 | case_mark | 否 | 备注 | 冒烟测试 |

### 验证规则

| 字段 | 验证规则 |
|------|----------|
| case_name | 不能为空 |
| case_tag | 不能为空 |
| case_level | 有效值: P0, P1, P2, P3, P4 (默认 P2) |
| case_type | 有效值: 1, 2, 3 (默认 1) |

---

## 错误码

| 错误信息 | 说明 | 处理方式 |
|----------|------|----------|
| 导入失败: 第X行: 用例标签不能为空 | case_tag 为空 | 修改 Excel 后重新上传 |
| 导入失败: 第X行: 用例名称不能为空 | case_name 为空 | 修改 Excel 后重新上传 |
| 预览数据已过期，请重新上传文件 | 缓存过期 | 重新执行 Step 1 |
| 该文件已提交过，不能重复提交 | 重复提交 | 使用新文件或等待过期 |
| 入库失败: xxx | 数据库错误 | 联系管理员 |