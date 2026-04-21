import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def _jwt_secret() -> str:
    secret = os.getenv("SECRET_KEY")
    if not secret:
        raise RuntimeError("SECRET_KEY is not set")
    return secret


def _jwt_algorithm() -> str:
    return os.getenv("ALGORITHM", "HS256")


def create_access_token(user_id: str, email: str) -> str:
    minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": user_id, "email": email, "type": "access", "exp": expire}
    return jwt.encode(payload, _jwt_secret(), algorithm=_jwt_algorithm())


def create_refresh_token(user_id: str, email: str) -> str:
    days = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    expire = datetime.now(timezone.utc) + timedelta(days=days)
    payload = {"sub": user_id, "email": email, "type": "refresh", "exp": expire}
    return jwt.encode(payload, _jwt_secret(), algorithm=_jwt_algorithm())


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[_jwt_algorithm()])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc

    return payload
