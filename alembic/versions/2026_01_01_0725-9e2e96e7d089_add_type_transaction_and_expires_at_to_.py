"""add_type_transaction_and_expires_at_to_payment_transactions

Revision ID: 9e2e96e7d089
Revises: 0ab246e09990
Create Date: 2026-01-01 07:25:25.219757

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e2e96e7d089'
down_revision: Union[str, Sequence[str], None] = '0ab246e09990'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add type_transaction column
    op.add_column('payment_transactions', 
        sa.Column('type_transaction', sa.String(), nullable=True)
    )
    
    # Add expires_at column
    op.add_column('payment_transactions', 
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove expires_at column
    op.drop_column('payment_transactions', 'expires_at')
    
    # Remove type_transaction column
    op.drop_column('payment_transactions', 'type_transaction')
