from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def _to_bcrypt_bytes(plain: str) -> bytes:
    """
    bcrypt only uses the first 72 bytes of a password and errors on longer
    input, so we truncate explicitly. Encoding first, then slicing bytes,
    avoids splitting a multi-byte UTF-8 character.
    """
    return plain.encode("utf-8")[:72]


def hash_password(plain: str) -> str:
    hashed = bcrypt.hashpw(_to_bcrypt_bytes(plain), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(_to_bcrypt_bytes(plain), hashed.encode("utf-8"))


def create_access_token(subject: str) -> str:
    """Create a signed JWT whose `sub` claim identifies the user (by email)."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> str | None:
    """Return the subject (email) from a valid token, or None if invalid/expired."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        return payload.get("sub")
    except JWTError:
        return None
