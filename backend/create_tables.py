"""Create SkillConnect tables in MySQL.

Run from the backend folder (venv active):
    python create_database.py
    python create_tables.py

Safe to run again: it only adds what is missing.
"""

import re

from sqlalchemy import inspect, text

from app.database import Base, engine
from app import models  # noqa: F401  (registers all tables on Base.metadata)


def migrate_user_roles():
    """Allow ADMIN in addition to CUSTOMER and PROVIDER."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE users MODIFY COLUMN role "
                "ENUM('CUSTOMER','PROVIDER','ADMIN') NOT NULL"
            )
        )


def safe_identifier(name):
    """Table and column names cannot be sent as SQL parameters, so we only accept
    plain names (letters, digits, underscore). They come from this file, never from users."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"Unsafe SQL name: {name!r}")
    return name


def safe_reference(reference):
    """Same idea for a foreign key target written like 'locations (id)'."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\s*\(\s*[A-Za-z_][A-Za-z0-9_]*\s*\)", reference):
        raise ValueError(f"Unsafe SQL reference: {reference!r}")
    return reference


def add_column_if_missing(table, column, definition):
    """create_all() never changes existing tables, so we add new columns ourselves."""
    safe_identifier(table)
    safe_identifier(column)
    existing = {col["name"] for col in inspect(engine).get_columns(table)}
    if column in existing:
        return
    with engine.begin() as connection:
        connection.execute(
            text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")  # audit-ok: names validated above
        )
    print(f"Added column {table}.{column}")


def add_foreign_key_if_missing(table, column, constraint, references):
    """Link table.column to another table's id (ON DELETE SET NULL)."""
    for name in (table, column, constraint):
        safe_identifier(name)
    safe_reference(references)
    foreign_keys = inspect(engine).get_foreign_keys(table)
    if any(fk["constrained_columns"] == [column] for fk in foreign_keys):
        return
    with engine.begin() as connection:
        connection.execute(
            text(  # audit-ok: names validated above
                f"ALTER TABLE {table} ADD CONSTRAINT {constraint} "
                f"FOREIGN KEY ({column}) REFERENCES {references} "
                "ON DELETE SET NULL"
            )
        )
    print(f"Added foreign key {table}.{column} -> {references}")


def migrate_step4():
    """Step 4: profile columns on users and provider_profiles."""
    add_column_if_missing("users", "bio", "TEXT NULL")
    add_column_if_missing("users", "photo_url", "VARCHAR(500) NULL")
    add_column_if_missing("users", "location_id", "INT NULL")
    add_column_if_missing("provider_profiles", "qualification", "VARCHAR(255) NULL")
    add_column_if_missing("provider_profiles", "working_area", "VARCHAR(255) NULL")
    add_column_if_missing("provider_profiles", "pricing_info", "VARCHAR(500) NULL")
    add_foreign_key_if_missing(
        "users", "location_id", "fk_users_location", "locations (id)"
    )


def migrate_step5():
    """Step 5: remember which provider added a custom skill."""
    add_column_if_missing("skills", "created_by_id", "INT NULL")
    add_foreign_key_if_missing(
        "skills", "created_by_id", "fk_skills_created_by", "users (id)"
    )


def migrate_step7():
    """Step 7: long-term request details on service_requests."""
    add_column_if_missing("service_requests", "start_date", "DATE NULL")
    add_column_if_missing("service_requests", "end_date", "DATE NULL")
    add_column_if_missing("service_requests", "working_days", "VARCHAR(80) NULL")
    add_column_if_missing("service_requests", "start_time", "TIME NULL")
    add_column_if_missing("service_requests", "end_time", "TIME NULL")
    add_column_if_missing("service_requests", "address_details", "VARCHAR(255) NULL")


def main():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    Base.metadata.create_all(bind=engine)
    migrate_user_roles()
    migrate_step4()
    migrate_step5()
    migrate_step7()

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Created/verified {len(tables)} tables in MySQL:")
    for name in sorted(tables):
        print(f" - {name}")


if __name__ == "__main__":
    main()
