from sqlalchemy import Engine, inspect, text

from app.db.base import Base


ISSUE_CONTRACT_COLUMN_BACKFILLS = {
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

PODCAST_CONTRACT_COLUMN_BACKFILLS = {
    "variant": "'standard'",
}


def _quote_identifier(engine: Engine, identifier: str) -> str:
    return engine.dialect.identifier_preparer.quote_identifier(identifier)


def _backfill_issue_contract_columns(engine: Engine) -> None:
    issue_table = _quote_identifier(engine, "issues")
    with engine.begin() as connection:
        current_columns = {
            row["name"]
            for row in connection.execute(text(f"PRAGMA table_info({issue_table})")).mappings()
        }
        for column_name, sql_default in ISSUE_CONTRACT_COLUMN_BACKFILLS.items():
            if column_name not in current_columns:
                continue
            column_identifier = _quote_identifier(engine, column_name)
            has_null = connection.execute(
                text(
                    f"SELECT 1 FROM {issue_table} "
                    f"WHERE {column_identifier} IS NULL "
                    "LIMIT 1",
                ),
            ).first()
            if not has_null:
                continue
            connection.execute(
                text(
                    f"UPDATE {issue_table} "
                    f"SET {column_identifier} = {sql_default} "
                    f"WHERE {column_identifier} IS NULL",
                ),
            )


def _backfill_podcast_contract_columns(engine: Engine) -> None:
    podcast_table = _quote_identifier(engine, "podcast_episodes")
    with engine.begin() as connection:
        current_columns = {
            row["name"]
            for row in connection.execute(text(f"PRAGMA table_info({podcast_table})")).mappings()
        }
        for column_name, sql_default in PODCAST_CONTRACT_COLUMN_BACKFILLS.items():
            if column_name not in current_columns:
                continue
            column_identifier = _quote_identifier(engine, column_name)
            has_null = connection.execute(
                text(
                    f"SELECT 1 FROM {podcast_table} "
                    f"WHERE {column_identifier} IS NULL "
                    "LIMIT 1",
                ),
            ).first()
            if has_null:
                connection.execute(
                    text(
                        f"UPDATE {podcast_table} "
                        f"SET {column_identifier} = {sql_default} "
                        f"WHERE {column_identifier} IS NULL",
                    ),
                )
        if {"generation_json", "variant"}.issubset(current_columns):
            connection.execute(
                text(
                    f"UPDATE {podcast_table} "
                    "SET variant = COALESCE(json_extract(generation_json, '$.variant'), variant, 'standard') "
                    "WHERE variant IS NULL OR variant = '' OR variant = 'standard'",
                ),
            )


def ensure_database_schema(engine: Engine) -> None:
    """Create new tables and patch additive SQLite columns for local dev DBs."""
    Base.metadata.create_all(bind=engine)
    if not engine.url.drivername.startswith("sqlite"):
        return

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            table_identifier = _quote_identifier(engine, table.name)
            current_columns = {
                row["name"]
                for row in connection.execute(text(f"PRAGMA table_info({table_identifier})")).mappings()
            }
            for column in table.columns:
                if column.name in current_columns:
                    continue
                column_type = column.type.compile(dialect=engine.dialect)
                column_identifier = _quote_identifier(engine, column.name)
                connection.execute(
                    text(f"ALTER TABLE {table_identifier} ADD COLUMN {column_identifier} {column_type}"),
                )
                current_columns.add(column.name)
            for index in table.indexes:
                if all(column.name in current_columns for column in index.columns):
                    index.create(bind=connection, checkfirst=True)

    if "issues" in existing_tables:
        _backfill_issue_contract_columns(engine)
    if "podcast_episodes" in existing_tables:
        _backfill_podcast_contract_columns(engine)
