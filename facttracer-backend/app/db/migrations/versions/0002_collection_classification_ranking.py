"""add collection classification ranking schema

Revision ID: 0002_collection_classification_ranking
Revises: 0001_initial
Create Date: 2026-06-10
"""

from collections.abc import Iterable

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = "0002_collection_classification_ranking"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


ISSUE_COLUMNS: list[sa.Column] = [
    sa.Column("major_topic_id", sa.String(length=80), nullable=True),
    sa.Column("event_group_id", sa.String(length=80), nullable=True),
    sa.Column("major_topic_name", sa.String(length=200), nullable=False, server_default=""),
    sa.Column("event_group_name", sa.String(length=240), nullable=False, server_default=""),
    sa.Column("representative_image_url", sa.Text(), nullable=False, server_default=""),
    sa.Column("representative_image_source", sa.String(length=200), nullable=False, server_default=""),
    sa.Column("representative_image_source_url", sa.Text(), nullable=False, server_default=""),
    sa.Column("representative_image_confidence", sa.Float(), nullable=False, server_default=sa.text("0.0")),
    sa.Column("representative_image_updated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("quality_score", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("quality_status", sa.String(length=60), nullable=False, server_default="unchecked"),
    sa.Column("quality_report_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("quality_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("last_quality_checked_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("next_quality_retry_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("ranking_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
]

ISSUE_DEFAULT_BACKFILLS = {
    "major_topic_name": "''",
    "event_group_name": "''",
    "representative_image_url": "''",
    "representative_image_source": "''",
    "representative_image_source_url": "''",
    "representative_image_confidence": "0.0",
    "quality_score": "0",
    "quality_status": "'unchecked'",
    "quality_report_json": "'{}'",
    "quality_attempts": "0",
    "ranking_json": "'{}'",
}


def _inspector() -> sa.Inspector:
    return inspect(op.get_bind())


def _tables() -> set[str]:
    return set(_inspector().get_table_names())


def _columns(table_name: str) -> set[str]:
    if table_name not in _tables():
        return set()
    return {column["name"] for column in _inspector().get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    if table_name not in _tables():
        return set()
    return {index["name"] for index in _inspector().get_indexes(table_name)}


def _quote(identifier: str) -> str:
    return op.get_bind().dialect.identifier_preparer.quote_identifier(identifier)


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if table_name in _tables() and column.name not in _columns(table_name):
        op.add_column(table_name, column)


def _create_index_if_missing(
    index_name: str,
    table_name: str,
    columns: Iterable[str],
    *,
    unique: bool = False,
) -> None:
    if table_name in _tables() and index_name not in _index_names(table_name):
        op.create_index(index_name, table_name, list(columns), unique=unique)


def _drop_index_if_exists(index_name: str, table_name: str) -> None:
    if table_name in _tables() and index_name in _index_names(table_name):
        op.drop_index(index_name, table_name=table_name)


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if table_name in _tables() and column_name in _columns(table_name):
        op.drop_column(table_name, column_name)


def _backfill_issue_defaults() -> None:
    if "issues" not in _tables():
        return
    issue_table = _quote("issues")
    existing_columns = _columns("issues")
    for column_name, sql_default in ISSUE_DEFAULT_BACKFILLS.items():
        if column_name not in existing_columns:
            continue
        column_identifier = _quote(column_name)
        op.execute(
            text(
                f"UPDATE {issue_table} "
                f"SET {column_identifier} = {sql_default} "
                f"WHERE {column_identifier} IS NULL",
            ),
        )


def _create_major_topics() -> None:
    if "major_topics" in _tables():
        return
    op.create_table(
        "major_topics",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=240), nullable=False),
        sa.Column("topic", sa.String(length=80), nullable=False, server_default="사회"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=60), nullable=False, server_default="active"),
        sa.Column("keywords_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("aliases_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("signal_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    )


def _create_event_groups() -> None:
    if "event_groups" in _tables():
        return
    op.create_table(
        "event_groups",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("major_topic_id", sa.String(length=80), nullable=True),
        sa.Column("topic", sa.String(length=80), nullable=False, server_default="사회"),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("slug", sa.String(length=280), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=60), nullable=False, server_default="active"),
        sa.Column("keywords_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("aliases_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("signal_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("article_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("issue_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    )


def _create_image_candidates() -> None:
    if "image_candidates" in _tables():
        return
    op.create_table(
        "image_candidates",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("issue_id", sa.String(length=80), nullable=True),
        sa.Column("article_id", sa.String(length=80), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("publisher", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("source_type", sa.String(length=80), nullable=False, server_default="news"),
        sa.Column("width", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("height", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("mime_type", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("status", sa.String(length=60), nullable=False, server_default="candidate"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def _create_user_interest_profiles() -> None:
    if "user_interest_profiles" in _tables():
        return
    op.create_table(
        "user_interest_profiles",
        sa.Column("user_id", sa.String(length=80), primary_key=True),
        sa.Column("topic_weights_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("major_topic_weights_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("event_group_weights_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("publisher_weights_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade() -> None:
    _create_major_topics()
    _create_event_groups()
    _create_image_candidates()
    _create_user_interest_profiles()

    for column in ISSUE_COLUMNS:
        _add_column_if_missing("issues", column)
    _backfill_issue_defaults()

    _create_index_if_missing("ix_major_topics_name", "major_topics", ["name"], unique=True)
    _create_index_if_missing("ix_major_topics_slug", "major_topics", ["slug"], unique=True)
    _create_index_if_missing("ix_major_topics_topic", "major_topics", ["topic"])
    _create_index_if_missing("ix_major_topics_status", "major_topics", ["status"])

    _create_index_if_missing("ix_event_groups_major_topic_id", "event_groups", ["major_topic_id"])
    _create_index_if_missing("ix_event_groups_topic", "event_groups", ["topic"])
    _create_index_if_missing("ix_event_groups_name", "event_groups", ["name"])
    _create_index_if_missing("ix_event_groups_slug", "event_groups", ["slug"])
    _create_index_if_missing("ix_event_groups_status", "event_groups", ["status"])

    _create_index_if_missing("ix_image_candidates_issue_id", "image_candidates", ["issue_id"])
    _create_index_if_missing("ix_image_candidates_article_id", "image_candidates", ["article_id"])
    _create_index_if_missing("ix_image_candidates_status", "image_candidates", ["status"])

    _create_index_if_missing("ix_issues_major_topic_id", "issues", ["major_topic_id"])
    _create_index_if_missing("ix_issues_event_group_id", "issues", ["event_group_id"])
    _create_index_if_missing("ix_issues_major_topic_name", "issues", ["major_topic_name"])
    _create_index_if_missing("ix_issues_event_group_name", "issues", ["event_group_name"])
    _create_index_if_missing("ix_issues_quality_status", "issues", ["quality_status"])


def downgrade() -> None:
    _drop_index_if_exists("ix_issues_quality_status", "issues")
    _drop_index_if_exists("ix_issues_event_group_name", "issues")
    _drop_index_if_exists("ix_issues_major_topic_name", "issues")
    _drop_index_if_exists("ix_issues_event_group_id", "issues")
    _drop_index_if_exists("ix_issues_major_topic_id", "issues")

    for column in reversed(ISSUE_COLUMNS):
        _drop_column_if_exists("issues", column.name)

    for index_name, table_name in [
        ("ix_image_candidates_status", "image_candidates"),
        ("ix_image_candidates_article_id", "image_candidates"),
        ("ix_image_candidates_issue_id", "image_candidates"),
        ("ix_event_groups_status", "event_groups"),
        ("ix_event_groups_slug", "event_groups"),
        ("ix_event_groups_name", "event_groups"),
        ("ix_event_groups_topic", "event_groups"),
        ("ix_event_groups_major_topic_id", "event_groups"),
        ("ix_major_topics_status", "major_topics"),
        ("ix_major_topics_topic", "major_topics"),
        ("ix_major_topics_slug", "major_topics"),
        ("ix_major_topics_name", "major_topics"),
    ]:
        _drop_index_if_exists(index_name, table_name)

    for table_name in [
        "user_interest_profiles",
        "image_candidates",
        "event_groups",
        "major_topics",
    ]:
        if table_name in _tables():
            op.drop_table(table_name)
