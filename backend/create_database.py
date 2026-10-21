"""Create the skillconnect MySQL database if it does not exist.

Run from the backend folder after filling MYSQL_PASSWORD in .env:
    python create_database.py
"""

import os
import re
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "skillconnect")

# A database name cannot be sent as a bound parameter, so it is checked
# strictly instead: letters, digits and underscore only.
if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", MYSQL_DATABASE):
    raise SystemExit("MYSQL_DATABASE may only contain letters, digits and _ (max 64).")

server_url = (
    f"mysql+pymysql://{MYSQL_USER}:{quote_plus(MYSQL_PASSWORD)}"
    f"@{MYSQL_HOST}:{MYSQL_PORT}/"
)


def main():
    engine = create_engine(server_url, pool_pre_ping=True)
    with engine.connect() as connection:
        connection.execute(
            text(  # audit-ok: name validated above
                f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )
        connection.commit()
    print(f"Database '{MYSQL_DATABASE}' is ready.")


if __name__ == "__main__":
    main()