"""rename interface fields to add interface_ prefix

Revision ID: 0001
Revises:
Create Date: 2026-04-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 重命名 interface 表的字段（添加 interface_ 前缀）
    op.alter_column('interface', 'name', new_column_name='interface_name')
    op.alter_column('interface', 'description', new_column_name='interface_desc')
    op.alter_column('interface', 'status', new_column_name='interface_status')
    op.alter_column('interface', 'level', new_column_name='interface_level')
    op.alter_column('interface', 'url', new_column_name='interface_url')
    op.alter_column('interface', 'method', new_column_name='interface_method')
    op.alter_column('interface', 'params', new_column_name='interface_params')
    op.alter_column('interface', 'headers', new_column_name='interface_headers')
    op.alter_column('interface', 'body_type', new_column_name='interface_body_type')
    op.alter_column('interface', 'raw_type', new_column_name='interface_raw_type')
    op.alter_column('interface', 'auth_type', new_column_name='interface_auth_type')
    op.alter_column('interface', 'auth', new_column_name='interface_auth')
    op.alter_column('interface', 'body', new_column_name='interface_body')
    op.alter_column('interface', 'data', new_column_name='interface_data')
    op.alter_column('interface', 'asserts', new_column_name='interface_asserts')
    op.alter_column('interface', 'extracts', new_column_name='interface_extracts')
    op.alter_column('interface', 'follow_redirects', new_column_name='interface_follow_redirects')
    op.alter_column('interface', 'connect_timeout', new_column_name='interface_connect_timeout')
    op.alter_column('interface', 'response_timeout', new_column_name='interface_response_timeout')
    op.alter_column('interface', 'before_script', new_column_name='interface_before_script')
    op.alter_column('interface', 'before_db_id', new_column_name='interface_before_db_id')
    op.alter_column('interface', 'before_sql', new_column_name='interface_before_sql')
    op.alter_column('interface', 'before_sql_extracts', new_column_name='interface_before_sql_extracts')
    op.alter_column('interface', 'after_script', new_column_name='interface_after_script')
    op.alter_column('interface', 'before_params', new_column_name='interface_before_params')

def downgrade() -> None:
    # 回滚：将字段名恢复为原来的名称
    op.alter_column('interface', 'interface_name', new_column_name='name')
    op.alter_column('interface', 'interface_desc', new_column_name='description')
    op.alter_column('interface', 'interface_status', new_column_name='status')
    op.alter_column('interface', 'interface_level', new_column_name='level')
    op.alter_column('interface', 'interface_url', new_column_name='url')
    op.alter_column('interface', 'interface_method', new_column_name='method')
    op.alter_column('interface', 'interface_params', new_column_name='params')
    op.alter_column('interface', 'interface_headers', new_column_name='headers')
    op.alter_column('interface', 'interface_body_type', new_column_name='body_type')
    op.alter_column('interface', 'interface_raw_type', new_column_name='raw_type')
    op.alter_column('interface', 'interface_auth_type', new_column_name='auth_type')
    op.alter_column('interface', 'interface_auth', new_column_name='auth')
    op.alter_column('interface', 'interface_body', new_column_name='body')
    op.alter_column('interface', 'interface_data', new_column_name='data')
    op.alter_column('interface', 'interface_asserts', new_column_name='asserts')
    op.alter_column('interface', 'interface_extracts', new_column_name='extracts')
    op.alter_column('interface', 'interface_follow_redirects', new_column_name='follow_redirects')
    op.alter_column('interface', 'interface_connect_timeout', new_column_name='connect_timeout')
    op.alter_column('interface', 'interface_response_timeout', new_column_name='response_timeout')
    op.alter_column('interface', 'interface_before_script', new_column_name='before_script')
    op.alter_column('interface', 'interface_before_db_id', new_column_name='before_db_id')
    op.alter_column('interface', 'interface_before_sql', new_column_name='before_sql')
    op.alter_column('interface', 'interface_before_sql_extracts', new_column_name='before_sql_extracts')
    op.alter_column('interface', 'interface_after_script', new_column_name='after_script')
    op.alter_column('interface', 'interface_before_params', new_column_name='before_params')
