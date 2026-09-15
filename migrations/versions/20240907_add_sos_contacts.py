"""Add SOS contacts table

Revision ID: 20240907_add_sos_contacts
Revises: e9c7e44ad8c5
Create Date: 2024-09-07

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '20240907_add_sos_contacts'
down_revision = 'e9c7e44ad8c5'
branch_labels = None
depends_on = None


def upgrade():
    # Crea la tabella sos_contacts
    op.create_table(
        'sos_contacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('relationship', sa.String(length=50), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Crea indice per query rapide
    op.create_index('ix_sos_contacts_user_id', 'sos_contacts', ['user_id'])
    op.create_index('ix_sos_contacts_user_priority', 'sos_contacts', ['user_id', 'priority'])


def downgrade():
    op.drop_index('ix_sos_contacts_user_priority', table_name='sos_contacts')
    op.drop_index('ix_sos_contacts_user_id', table_name='sos_contacts')
    op.drop_table('sos_contacts')
