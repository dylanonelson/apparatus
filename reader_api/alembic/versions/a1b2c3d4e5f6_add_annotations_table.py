"""add annotations table

Revision ID: a1b2c3d4e5f6
Revises: 3e0c1f7842d9
Create Date: 2026-03-16 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "3e0c1f7842d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # The annotation_color enum is created implicitly by the column definition
    annotation_color = postgresql.ENUM(
        "yellow", "blue", "green", "pink", "purple",
        name="annotation_color",
        create_type=False,
    )
    # Explicitly create the enum type first
    op.execute("CREATE TYPE annotation_color AS ENUM ('yellow', 'blue', 'green', 'pink', 'purple')")

    op.create_table(
        "annotations",
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
            comment="User who owns this annotation",
        ),
        sa.Column(
            "publication_id",
            sa.String(length=255),
            nullable=False,
            comment="Publication identifier",
        ),
        sa.Column(
            "locator",
            sa.JSON(),
            nullable=False,
            comment="Readium locator object pinpointing the annotated passage",
        ),
        sa.Column(
            "color",
            annotation_color,
            nullable=False,
            comment="Highlight color",
        ),
        sa.Column(
            "user_note",
            sa.Text(),
            nullable=True,
            comment="User-authored note attached to the highlight",
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp supplied by the client for this annotation",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Timestamp when the annotation was created",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Timestamp when the annotation was last updated",
        ),
    )
    op.create_index(
        "ix_annotations_user_pub",
        "annotations",
        ["user_id", "publication_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_annotations_user_pub", table_name="annotations")
    op.drop_table("annotations")
    op.execute("DROP TYPE IF EXISTS annotation_color")
