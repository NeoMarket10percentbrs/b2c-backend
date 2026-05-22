from alembic import op

revision = '14017dceacbe'
down_revision = 'dd3d672c8042'
branch_labels = None
depends_on = None


def upgrade():
    statuses = [
        "CREATED",
        "PAID",
        "ASSEMBLING",
        "DELIVERING",
        "DELIVERED",
        "CANCELLED",
        "CANCEL_PENDING",
    ]
    for status in statuses:
        op.execute("COMMIT")  # Exit the current transaction block
        op.execute(f"ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS '{status}'")


def downgrade():
    pass  # Enum values cannot be removed in PostgreSQL without recreating the type