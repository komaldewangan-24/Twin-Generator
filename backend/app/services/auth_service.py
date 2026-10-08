from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user import User
from app.utils.security import hash_password, verify_password


def get_user_by_email(db: Session, email: str) -> User | None:
    # Case-insensitive: A@x.com and a@x.com are the same person.
    return db.query(User).filter(func.lower(User.email) == email.strip().lower()).first()


def create_user(db: Session, email: str, password: str) -> User | None:
    if get_user_by_email(db, email):
        return None
    user = User(email=email.strip().lower(), password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        return None
    return user
