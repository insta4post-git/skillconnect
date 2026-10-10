"""Create an ADMIN user from .env (ADMIN_EMAIL, ADMIN_PASSWORD).

Public registration cannot create an admin.
Run from the backend folder:
    python create_admin.py
"""

import os

from dotenv import load_dotenv

from app.crud import create_user, get_user_by_email
from app.database import SessionLocal
from app.models import UserRole

load_dotenv()


def main():
    email = os.getenv("ADMIN_EMAIL", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "").strip()
    name = os.getenv("ADMIN_NAME", "SkillConnect Admin").strip()

    if not email or not password:
        print("Set ADMIN_EMAIL and ADMIN_PASSWORD in backend/.env first.")
        return
    if len(password) < 8:
        print("ADMIN_PASSWORD must be at least 8 characters.")
        return

    db = SessionLocal()
    try:
        existing = get_user_by_email(db, email)
        if existing:
            print(f"User {email} already exists with role {existing.role.value}.")
            return
        user = create_user(
            db,
            full_name=name,
            email=email,
            password=password,
            role=UserRole.ADMIN,
        )
        print(f"Admin created: {user.email} (id={user.id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
