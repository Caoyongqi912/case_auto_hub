"""add content_name to interface_case_step_content

Revision ID: 2026_04_10_0001
Revises: 0001
Create Date: 2026-04-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '2026_04_10_0001'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('interface_case_step_content', sa.Column('content_name', sa.String(length=100), nullable=True, comment='自定义名称'))

def downgrade() -> None:
    op.drop_column('interface_case_step_content', 'content_name')
