"""add owner_id fk to bookmarks

Revision ID: 20a5d3e9eefc
Revises: 6d55114755b9
Create Date: 2026-08-25 06:40:46.655676

Hand-adjusted: autogenerate's plain op.add_column + op.create_foreign_key
fails outright on SQLite - "No support for ALTER of constraints in SQLite
dialect." SQLite's own ALTER TABLE can't add a constraint to an existing
table at all. Alembic's documented workaround is *batch mode*: instead of
altering bookmarks in place, it builds a new table with the target shape,
copies every row across, drops the old table, and renames the new one into
place - which is exactly what "add a constraint to an existing table" has
to mean when the underlying database can't do it directly. The constraint
is named explicitly (autogenerate left it None) so downgrade() has an
actual name to drop instead of relying on SQLite to invent one.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20a5d3e9eefc'
down_revision: Union[str, None] = '6d55114755b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("bookmarks") as batch_op:
        batch_op.add_column(sa.Column("owner_id", sa.Integer(), nullable=False))
        batch_op.create_foreign_key(
            "fk_bookmarks_owner_id_users", "users", ["owner_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("bookmarks") as batch_op:
        batch_op.drop_constraint("fk_bookmarks_owner_id_users", type_="foreignkey")
        batch_op.drop_column("owner_id")
