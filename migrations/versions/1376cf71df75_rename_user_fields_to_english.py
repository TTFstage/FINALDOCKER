"""rename user fields to english

Revision ID: 1376cf71df75
Revises: a9b79dc69fb6
Create Date: 2026-09-17 15:10:28.292257

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '1376cf71df75'
down_revision = 'a9b79dc69fb6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tax_id_code', sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column('full_name', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('date_of_birth', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('gender', sa.String(length=1), nullable=True))
        batch_op.add_column(sa.Column('birth_city_country', sa.String(length=200), nullable=True))
        batch_op.drop_constraint('user_codice_fiscale_key', type_='unique')
        batch_op.create_unique_constraint(None, ['tax_id_code'])
        batch_op.drop_column('comune_stato_nascita')
        batch_op.drop_column('data_nascita')
        batch_op.drop_column('codice_fiscale')
        batch_op.drop_column('nome_cognome')
        batch_op.drop_column('sesso')


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sesso', sa.VARCHAR(length=1), nullable=True))
        batch_op.add_column(sa.Column('nome_cognome', sa.VARCHAR(length=200), nullable=True))
        batch_op.add_column(sa.Column('codice_fiscale', sa.VARCHAR(length=16), nullable=True))
        batch_op.add_column(sa.Column('data_nascita', sa.DATE(), nullable=True))
        batch_op.add_column(sa.Column('comune_stato_nascita', sa.VARCHAR(length=200), nullable=True))
        batch_op.drop_constraint(None, type_='unique')
        batch_op.create_unique_constraint('user_codice_fiscale_key', ['codice_fiscale'])
        batch_op.drop_column('birth_city_country')
        batch_op.drop_column('gender')
        batch_op.drop_column('date_of_birth')
        batch_op.drop_column('full_name')
        batch_op.drop_column('tax_id_code')
