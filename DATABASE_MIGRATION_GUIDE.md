# 数据库迁移指南

## 项目现状

你的 FastAPI 项目当前使用的是 SQLAlchemy ORM，但**没有配置数据库迁移工具**。

当前在 `app/model/__init__.py` 中的 `create_table()` 函数只会：
- ✅ 创建新表（如果不存在）
- ❌ **不会**更新现有表的结构
- ❌ **不会**删除旧字段
- ❌ **不会**修改字段类型

这意味着当你修改模型（如将 `name` 重命名为 `interface_name`）时，数据库表**不会自动更新**。

## 解决方案

我为你提供了**两套方案**，你可以根据场景选择使用：

---

## 方案一：Alembic（推荐用于生产环境）⭐

### 为什么推荐 Alembic？

- 📋 **版本化管理**：所有数据库变更都有版本记录
- 🔄 **可回滚**：可以轻松回滚到任意版本
- 🎯 **精确控制**：可以控制每个字段的变更
- 🚀 **团队协作**：适合多人开发，可以通过 Git 管理迁移脚本
- ⚡ **自动化生成**：可以自动检测模型变更并生成迁移脚本

### 已创建的文件

```
case_auto_hub/
├── alembic/
│   ├── env.py                 # Alembic 环境配置
│   ├── script.py.mako         # 迁移脚本模板
│   ├── README
│   └── versions/
│       └── 2026_04_07_0001_add_interface_prefix.py  # 示例迁移
├── alembic.ini                # Alembic 配置文件
└── migrate.py                 # 便捷迁移管理脚本
```

### 快速开始

#### 1. 安装依赖

```bash
pip install alembic aiomysql
```

#### 2. 初始化（首次使用）

首次使用需要初始化数据库：

```bash
python migrate.py init
```

#### 3. 修改模型后，生成迁移脚本

当你修改了模型（如添加字段、修改字段）后：

```bash
# 自动检测变更并生成迁移脚本
python migrate.py migrate

# 给迁移一个描述性名称
alembic revision --autogenerate -m "add user_email field"
```

Alembic 会自动检测到你模型的变化，并生成迁移脚本。

#### 4. 执行迁移

```bash
# 查看将要执行的操作（预览）
alembic upgrade --sql

# 实际执行迁移
python migrate.py upgrade

# 或者一步步来
alembic upgrade head
```

#### 5. 查看当前版本

```bash
python migrate.py show
# 或
alembic current
```

#### 6. 回滚（如有需要）

```bash
# 回滚到上一个版本
python migrate.py downgrade

# 回滚到指定版本
python migrate.py downgrade <revision_id>

# 回滚所有迁移
alembic downgrade base
```

### 处理你的字段重命名

对于你提到的从 `name` → `interface_name` 的变更，示例迁移脚本已创建：

📄 `alembic/versions/2026_04_07_0001_add_interface_prefix.py`

这个脚本会：
- 将 `interface` 表的所有字段重命名（添加 `interface_` 前缀）
- 包括完整的 `upgrade()` 和 `downgrade()` 函数
- 可以直接使用，无需修改

**执行迁移：**

```bash
# 如果还没有执行过迁移
python migrate.py upgrade

# 如果需要回滚
python migrate.py downgrade
```

---

## 方案二：自动同步脚本（仅用于开发环境）⚠️

### 警告

⚠️ **此方案仅适用于开发/测试环境！**

原因：
- 会直接修改数据库结构，没有版本记录
- 无法回滚
- 可能导致数据丢失（如果删除字段）
- 没有精细控制

### 使用场景

- 本地开发时快速同步表结构
- 快速原型开发
- 测试环境重建数据库

### 快速开始

#### 1. 预览更改（推荐先执行）

```bash
python sync_database.py --dry-run
```

输出示例：

```
============================================================
数据库同步分析报告
============================================================

数据库中存在的表: 25
模型中定义的表: 28

⚠️  仅在数据库中存在的表（不会被删除）:
   - old_table

✅  仅在模型中存在的表（将被创建）:
   + interfaceAPIModel

📝  表结构对比:

   表: interface
      新增字段:
        + interface_name (VARCHAR(100))
        + interface_desc (TEXT)
      缺失字段（模型中已移除）:
        - name
        - description
```

#### 2. 执行同步

```bash
python sync_database.py --execute
```

**注意**：
- ✅ 会创建新表
- ✅ 会添加新字段
- ❌ **不会**删除数据列（安全）
- ❌ **不会**修改现有字段类型（安全）

### 为什么不能删除字段？

`BaseModel.metadata.create_all()` 只会创建不存在的表和字段，**不会**删除或修改现有的。

如果你需要删除字段或修改字段类型，只能使用：
1. **Alembic**（推荐）
2. **手动 SQL**：

```sql
-- 删除字段
ALTER TABLE interface DROP COLUMN old_field;

-- 修改字段
ALTER TABLE interface MODIFY COLUMN name VARCHAR(200);
```

---

## 最佳实践

### 开发流程建议

#### 1. 本地开发（使用 sync_database.py）

```bash
# 每次修改模型后
python sync_database.py --dry-run   # 预览
python sync_database.py --execute   # 同步
```

#### 2. 测试/预生产环境（使用 Alembic）

```bash
# 生成迁移脚本
alembic revision --autogenerate -m "describe your changes"

# 审查生成的脚本
cat alembic/versions/xxxx_description.py

# 执行迁移
alembic upgrade head
```

#### 3. 生产环境（使用 Alembic）

```bash
# 在测试环境验证迁移脚本
alembic upgrade head

# 备份数据库
mysqldump -u root -p autoHub > backup.sql

# 部署迁移脚本到生产
alembic upgrade head
```

### 模型设计建议

#### ❌ 避免频繁重命名字段

字段重命名（如 `name` → `interface_name`）会导致：
- 需要编写复杂的迁移脚本
- 风险较高
- 历史数据需要迁移

#### ✅ 推荐做法

1. **添加新字段，而非重命名**
   ```python
   # 不好：重命名
   name = Column(String(100))  # 旧
   interface_name = Column(String(100))  # 新

   # 好：添加新字段，保留旧字段一段时间
   name = Column(String(100))
   interface_name = Column(String(100), nullable=True)  # 新增
   ```

2. **使用 nullable 字段进行平滑迁移**
   ```python
   # 添加新字段，允许为空
   interface_name = Column(String(100), nullable=True)

   # 逐步将数据迁移到新字段
   UPDATE interface SET interface_name = name WHERE interface_name IS NULL;

   # 确保数据迁移完成后，再将旧字段设为 nullable=False
   # 最后才删除旧字段
   ```

3. **使用 Alembic 的批量迁移脚本**

   为你的字段重命名创建专门的迁移脚本：

   ```python
   # alembic/versions/2026_04_07_rename_interface_fields.py

   def upgrade():
       # 1. 添加新字段
       op.add_column('interface', Column('interface_name', String(100)))
       # ... 添加其他新字段

       # 2. 迁移数据
       op.execute("UPDATE interface SET interface_name = name")

       # 3. 删除旧字段
       op.drop_column('interface', 'name')
   ```

### 团队协作

1. **迁移脚本纳入版本控制**
   ```bash
   git add alembic/
   git commit -m "add migration for interface fields rename"
   ```

2. **每个开发者拉取最新迁移**
   ```bash
   git pull
   alembic upgrade head
   ```

3. **禁止直接修改已部署的迁移脚本**

---

## 常见问题

### Q1: 如何查看 Alembic 生成的脚本？

```bash
# 列出所有迁移
alembic history

# 查看某个迁移的详细信息
alembic show <revision>

# 查看当前状态
alembic current
alembic check
```

### Q2: 迁移失败怎么办？

```bash
# 查看错误日志
alembic upgrade head --sql  # 加上 --sql 可以看到实际执行的 SQL

# 手动修复后，继续迁移
alembic upgrade head
```

### Q3: 如何同时管理多个数据库？

在 `alembic.ini` 中配置多个数据库：

```ini
[databases]
pro = mysql://user:pass@pro-db/autoHub
test = mysql://user:pass@test-db/autoHub
```

使用时指定数据库：

```bash
alembic upgrade head -n databases.pro
```

### Q4: 可以在 FastAPI 启动时自动迁移吗？

可以，但**不推荐**（生产环境）。如果确实需要：

```python
# main.py
@app.on_event("startup")
async def startup_event():
    # 仅在开发环境使用
    if Config.ENV == "dev":
        result = subprocess.run(["alembic", "upgrade", "head"])
        if result.returncode != 0:
            raise Exception("数据库迁移失败")
```

### Q5: 模型中移除字段，但数据库还有这个字段？

这是**正常的**，没有问题：
- 模型中未定义的字段会被 SQLAlchemy 忽略
- 数据仍然在数据库中，只是 ORM 不再使用
- 可以手动清理：`ALTER TABLE DROP COLUMN old_field;`

---

## 总结

### 推荐方案

| 场景 | 推荐方案 | 原因 |
|------|---------|------|
| 生产环境 | Alembic ⭐ | 版本化管理，可回滚，安全 |
| 测试环境 | Alembic | 需要验证迁移脚本 |
| 开发环境 | sync_database.py | 快速迭代 |
| 原型开发 | sync_database.py | 快速验证 |

### 下一步操作

1. ✅ **立即执行**：`pip install alembic aiomysql`
2. ✅ **初始化**：在本地执行 `python migrate.py init`
3. ✅ **查看示例**：检查 `alembic/versions/2026_04_07_0001_add_interface_prefix.py`
4. ✅ **执行迁移**：将示例迁移应用到你的数据库
5. ✅ **添加到 Git**：将 `alembic/` 目录提交到版本控制

---

## 附录：常用命令速查

```bash
# 安装
pip install alembic aiomysql

# 初始化（新项目）
alembic init alembic

# 生成迁移
alembic revision --autogenerate -m "message"

# 执行迁移
alembic upgrade head

# 回滚
alembic downgrade -1

# 查看状态
alembic current
alembic history

# 清空所有迁移（危险！）
alembic downgrade base
```

---

**祝你开发顺利！** 🚀
