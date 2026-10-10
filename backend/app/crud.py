from sqlalchemy.orm import Session

from app.models import User, UserRole
from app.security import hash_password


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.lower().strip()).first()


def create_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    password: str,
    role: UserRole,
    phone: str | None = None,
) -> User:
    user = User(
        full_name=full_name.strip(),
        email=email.lower().strip(),
        password_hash=hash_password(password),
        role=role,
        phone=phone.strip() if phone else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
