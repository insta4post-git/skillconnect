"""Create SkillConnect tables in MySQL.

Run from the backend folder (venv active):
    python create_database.py
    python create_tables.py
"""

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


def main():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    Base.metadata.create_all(bind=engine)
    migrate_user_roles()

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Created/verified {len(tables)} tables in MySQL:")
    for name in sorted(tables):
        print(f" - {name}")


if __name__ == "__main__":
    main()
