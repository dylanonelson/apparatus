"""add selection text to viewport

Revision ID: 3e0c1f7842d9
Revises: c4f24ad9b8f0
Create Date: 2025-12-04 14:27:24.186265

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3e0c1f7842d9"
down_revision: Union[str, Sequence[str], None] = "c4f24ad9b8f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "viewports",
        sa.Column(
            "selection_text",
            sa.Text(),
            nullable=True,
            comment="Text currently selected by the user within the viewport",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("viewports", "selection_text")
