"""add viewports table

Revision ID: c4f24ad9b8f0
Revises: 27b0c39f4a9c
Create Date: 2025-11-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c4f24ad9b8f0"
down_revision: Union[str, Sequence[str], None] = "27b0c39f4a9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "viewports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="User associated with the viewport snapshot",
        ),
        sa.Column(
            "publication_id",
            sa.String(length=255),
            nullable=False,
            comment="Publication identifier",
        ),
        sa.Column(
            "positions",
            sa.JSON(),
            nullable=False,
            comment="Positions currently visible to the user from the positions list",
        ),
        sa.Column(
            "text",
            sa.Text(),
            nullable=False,
            comment="Full text currently visible to the user",
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp supplied by the client for this viewport snapshot",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            comment="Timestamp when the viewport snapshot was last updated",
        ),
        sa.UniqueConstraint("user_id", name="uq_viewports_user_id"),
    )
    op.create_index(
        "ix_viewports_user_id",
        "viewports",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_viewports_user_pub_updated_at",
        "viewports",
        ["user_id", "publication_id", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_viewports_user_pub_updated_at", table_name="viewports")
    op.drop_index("ix_viewports_user_id", table_name="viewports")
    op.drop_table("viewports")
