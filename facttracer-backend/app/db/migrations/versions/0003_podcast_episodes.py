"""add podcast episodes

Revision ID: 0003_podcast_episodes
Revises: 0002_collection_classification_ranking
Create Date: 2026-06-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0003_podcast_episodes"
down_revision = "0002_collection_classification_ranking"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _index_names(table_name: str) -> set[str]:
    if table_name not in _tables():
        return set()
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if table_name in _tables() and index_name not in _index_names(table_name):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    if "podcast_episodes" not in _tables():
        op.create_table(
            "podcast_episodes",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("issue_id", sa.String(length=80), nullable=True),
            sa.Column("title", sa.String(length=260), nullable=False),
            sa.Column("subtitle", sa.String(length=260), nullable=False, server_default=""),
            sa.Column("summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("category", sa.String(length=80), nullable=False, server_default="사회"),
            sa.Column("episode_type", sa.String(length=60), nullable=False, server_default="issue"),
            sa.Column("episode_format", sa.String(length=40), nullable=False, server_default="solo"),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="published"),
            sa.Column("audio_url", sa.Text(), nullable=False, server_default=""),
            sa.Column("thumbnail_url", sa.Text(), nullable=False, server_default=""),
            sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("host_profiles_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("script_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("source_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("rank_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("generation_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("auto_published", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("issue_id", "episode_format", name="uq_podcast_episode_issue_format"),
        )
    _create_index_if_missing("ix_podcast_episodes_issue_id", "podcast_episodes", ["issue_id"])
    _create_index_if_missing("ix_podcast_episodes_title", "podcast_episodes", ["title"])
    _create_index_if_missing("ix_podcast_episodes_category", "podcast_episodes", ["category"])
    _create_index_if_missing("ix_podcast_episodes_episode_type", "podcast_episodes", ["episode_type"])
    _create_index_if_missing("ix_podcast_episodes_status", "podcast_episodes", ["status"])


def downgrade() -> None:
    if "podcast_episodes" in _tables():
        op.drop_table("podcast_episodes")
