import hashlib
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import RefreshToken, User


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def validate_password_strength(password: str) -> None:
    """Validate password meets security requirements.

    Raises ValueError with specific message if password doesn't meet requirements.
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(password) > 128:
        raise ValueError("Password must not exceed 128 characters")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/~`]', password):
        raise ValueError("Password must contain at least one special character")


def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "iat": now,  # Issued at
        "iss": "base-client-server",  # Issuer
        "aud": "base-client-server-api",  # Audience
        "type": "access",
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token. Raises jwt.PyJWTError on failure."""
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        issuer="base-client-server",
        audience="base-client-server-api",
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    return payload


def generate_refresh_token() -> tuple[str, str]:
    """Returns (raw_token, sha256_hash)."""
    raw = secrets.token_urlsafe(48)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, email: str, password: str) -> User:
    """Create a new user. Flushes only — caller is responsible for committing."""
    validate_password_strength(password)
    user = User(email=email, hashed_password=hash_password(password))
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def create_refresh_token_record(db: AsyncSession, user_id: uuid.UUID) -> str:
    """Create a refresh token in the DB. Returns the raw token (for the cookie).

    Only flushes (does not commit) — caller is responsible for committing the transaction.
    """
    raw_token, token_hash = generate_refresh_token()
    record = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC)
        + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(record)
    await db.flush()
    return raw_token


async def rotate_refresh_token(db: AsyncSession, raw_token: str) -> tuple[User, str]:
    """Validate, revoke, and reissue a refresh token. Returns (user, new_raw_token).

    Raises ValueError if the token is invalid, expired, or already revoked.
    Uses SELECT FOR UPDATE to prevent concurrent rotation of the same token.
    """
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    result = await db.execute(
        select(RefreshToken)
        .where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
        .with_for_update()
    )
    record = result.scalar_one_or_none()

    if record is None:
        raise ValueError("Invalid refresh token")
    if record.expires_at < datetime.now(UTC):
        raise ValueError("Refresh token expired")

    # Revoke the old token
    record.revoked_at = datetime.now(UTC)

    # Load user
    user_result = await db.execute(select(User).where(User.id == record.user_id))
    user = user_result.scalar_one()

    # Issue new token (flush only, we commit the whole transaction here)
    new_raw_token = await create_refresh_token_record(db, user.id)
    await db.commit()
    return user, new_raw_token


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> None:
    """Revoke a refresh token (logout)."""
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
    )
    record = result.scalar_one_or_none()
    if record:
        record.revoked_at = datetime.now(UTC)
        await db.commit()
