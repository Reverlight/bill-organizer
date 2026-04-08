"""fix two primary keys

Revision ID: a023f4a05d2f
Revises: 3a0a7a3aab0c
Create Date: 2026-04-08 07:52:59.097352

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a023f4a05d2f'
down_revision: Union[str, Sequence[str], None] = '3a0a7a3aab0c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # drop the composite primary key (file_id, id)
    op.drop_constraint('pk_receipts', 'receipts', type_='primary')
    # recreate with only id as primary key
    op.create_primary_key('pk_receipts', 'receipts', ['id'])
    # now file_id can be nullable and drop the index
    op.alter_column('receipts', 'file_id',
                    existing_type=sa.VARCHAR(),
                    nullable=True)
    op.drop_index(op.f('ix_receipts_file_id'), table_name='receipts')


def downgrade() -> None:
    op.create_index(op.f('ix_receipts_file_id'), 'receipts', ['file_id'], unique=False)
    op.alter_column('receipts', 'file_id',
                    existing_type=sa.VARCHAR(),
                    nullable=False)
    op.drop_constraint('pk_receipts', 'receipts', type_='primary')
    op.create_primary_key('pk_receipts', 'receipts', ['file_id', 'id'])
