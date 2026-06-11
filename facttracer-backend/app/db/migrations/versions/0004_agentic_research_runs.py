"""add agentic research runs

Revision ID: 0004_agentic_research_runs
Revises: 0003_podcast_episodes
Create Date: 2026-06-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0004_agentic_research_runs"
down_revision = "0003_podcast_episodes"
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


def _drop_index_if_exists(index_name: str, table_name: str) -> None:
    if table_name in _tables() and index_name in _index_names(table_name):
        op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    if "research_runs" not in _tables():
        op.create_table(
            "research_runs",
            sa.Column("id", sa.String(length=80), primary_key=True),
            sa.Column("issue_id", sa.String(length=80), nullable=True),
            sa.Column("discovery_topic_id", sa.String(length=80), nullable=True),
            sa.Column("keyword_id", sa.String(length=80), nullable=True),
            sa.Column("trigger_type", sa.String(length=80), nullable=False, server_default="manual"),
            sa.Column("seed_query", sa.String(length=300), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=80), nullable=False, server_default="running"),
            sa.Column("round_index", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("plan_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("source_routes_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("executed_queries_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("result_urls_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("selected_article_ids_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("missing_signals_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        )
    _create_index_if_missing("ix_research_runs_issue_id", "research_runs", ["issue_id"])
    _create_index_if_missing("ix_research_runs_discovery_topic_id", "research_runs", ["discovery_topic_id"])
    _create_index_if_missing("ix_research_runs_keyword_id", "research_runs", ["keyword_id"])
    _create_index_if_missing("ix_research_runs_trigger_type", "research_runs", ["trigger_type"])
    _create_index_if_missing("ix_research_runs_status", "research_runs", ["status"])


def downgrade() -> None:
    _drop_index_if_exists("ix_research_runs_status", "research_runs")
    _drop_index_if_exists("ix_research_runs_trigger_type", "research_runs")
    _drop_index_if_exists("ix_research_runs_keyword_id", "research_runs")
    _drop_index_if_exists("ix_research_runs_discovery_topic_id", "research_runs")
    _drop_index_if_exists("ix_research_runs_issue_id", "research_runs")
    if "research_runs" in _tables():
        op.drop_table("research_runs")
