"""add podcast episode variants

Revision ID: 0005_podcast_episode_variants
Revises: 0004_agentic_research_runs
Create Date: 2026-06-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0005_podcast_episode_variants"
down_revision = "0004_agentic_research_runs"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _columns(table_name: str) -> set[str]:
    if table_name not in _tables():
        return set()
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    if table_name not in _tables():
        return set()
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(table_name)}


def _unique_constraints(table_name: str) -> set[str]:
    if table_name not in _tables():
        return set()
    return {
        constraint["name"]
        for constraint in inspect(op.get_bind()).get_unique_constraints(table_name)
        if constraint.get("name")
    }


def upgrade() -> None:
    if "podcast_episodes" not in _tables():
        return

    if "variant" not in _columns("podcast_episodes"):
        op.add_column(
            "podcast_episodes",
            sa.Column("variant", sa.String(length=40), nullable=False, server_default="standard"),
        )

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            UPDATE podcast_episodes
            SET variant = COALESCE(generation_json->>'variant', variant, 'standard')
            WHERE variant IS NULL OR variant = '' OR variant = 'standard'
            """,
        )
    elif dialect == "sqlite":
        op.execute(
            """
            UPDATE podcast_episodes
            SET variant = COALESCE(json_extract(generation_json, '$.variant'), variant, 'standard')
            WHERE variant IS NULL OR variant = '' OR variant = 'standard'
            """,
        )

    unique_names = _unique_constraints("podcast_episodes")
    if "uq_podcast_episode_issue_format_variant" not in unique_names:
        with op.batch_alter_table("podcast_episodes") as batch_op:
            if "uq_podcast_episode_issue_format" in unique_names:
                batch_op.drop_constraint("uq_podcast_episode_issue_format", type_="unique")
            batch_op.create_unique_constraint(
                "uq_podcast_episode_issue_format_variant",
                ["issue_id", "episode_format", "variant"],
            )

    if "ix_podcast_episodes_variant" not in _indexes("podcast_episodes"):
        op.create_index("ix_podcast_episodes_variant", "podcast_episodes", ["variant"])


def downgrade() -> None:
    if "podcast_episodes" not in _tables():
        return

    unique_names = _unique_constraints("podcast_episodes")
    if "uq_podcast_episode_issue_format_variant" in unique_names:
        with op.batch_alter_table("podcast_episodes") as batch_op:
            batch_op.drop_constraint("uq_podcast_episode_issue_format_variant", type_="unique")
            batch_op.create_unique_constraint(
                "uq_podcast_episode_issue_format",
                ["issue_id", "episode_format"],
            )

    if "ix_podcast_episodes_variant" in _indexes("podcast_episodes"):
        op.drop_index("ix_podcast_episodes_variant", table_name="podcast_episodes")
    if "variant" in _columns("podcast_episodes"):
        op.drop_column("podcast_episodes", "variant")
