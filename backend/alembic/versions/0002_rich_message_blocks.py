"""Add structured rich-content blocks to messages.

Revision ID: 0002_rich_message_blocks
Revises: 0001_initial
"""

import sqlalchemy as sa

from alembic import op

revision = "0002_rich_message_blocks"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("messages")}
    if "content_blocks" not in columns:
        op.add_column("messages", sa.Column("content_blocks", sa.JSON(), nullable=True))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("messages")}
    if "content_blocks" in columns:
        op.drop_column("messages", "content_blocks")
