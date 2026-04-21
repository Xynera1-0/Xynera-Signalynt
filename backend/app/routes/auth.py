import os
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from psycopg2 import OperationalError
from psycopg2.errors import UniqueViolation

from ..db import get_db_cursor
from ..security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)
_schema_lock = Lock()
_password_hash_ready = False
_google_auth_ready = False


def _raise_db_http_exception(exc: Exception) -> None:
    if isinstance(exc, OperationalError):
        raise HTTPException(status_code=503, detail="Database unavailable. Please try again.")

    raise HTTPException(status_code=500, detail=f"Database error: {exc}")


class RegisterRequest(BaseModel):
    name: str | None = None
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(min_length=10)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10)


def _ensure_password_hash_column() -> None:
    """Ensure password hash column exists on public.users."""
    global _password_hash_ready

    if _password_hash_ready:
        return

    with _schema_lock:
        if _password_hash_ready:
            return

        query = """
            ALTER TABLE public.users
            ADD COLUMN IF NOT EXISTS password_hash text;
        """
        with get_db_cursor() as cursor:
            cursor.execute(query)

        _password_hash_ready = True


def _ensure_google_auth_columns() -> None:
    global _google_auth_ready

    if _google_auth_ready:
        return

    with _schema_lock:
        if _google_auth_ready:
            return

        with get_db_cursor() as cursor:
            cursor.execute(
                """
                ALTER TABLE public.users
                ADD COLUMN IF NOT EXISTS google_sub text;
                """
            )
            cursor.execute(
                """
                ALTER TABLE public.users
                ADD COLUMN IF NOT EXISTS auth_provider text DEFAULT 'local';
                """
            )

        _google_auth_ready = True


def _google_client_id() -> str:
    client_id = (
        os.getenv("GOOGLE_CLIENT_ID")
        or os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        or os.getenv("NEXT_PUBLIC_GOOGLE_CLIENT_ID")
    )
    if not client_id:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID is not configured")
    return client_id


def _token_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    if credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid auth scheme")

    try:
        payload = decode_token(credentials.credentials)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid access token")

    user_id = payload.get("sub")
    email = payload.get("email")
    if not user_id or not email:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    return {"user_id": user_id, "email": email}


@router.post("/register")
def register_user(payload: RegisterRequest):
    query = """
        INSERT INTO public.users (name, email, password_hash)
        VALUES (%s, %s, %s)
        RETURNING id, name, email, created_at;
    """

    try:
        _ensure_password_hash_column()
        with get_db_cursor() as cursor:
            cursor.execute(
                query,
                (payload.name, payload.email, hash_password(payload.password)),
            )
            user = cursor.fetchone()
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="Email already registered")
    except Exception as exc:
        _raise_db_http_exception(exc)

    access_token = create_access_token(str(user["id"]), user["email"])
    refresh_token = create_refresh_token(str(user["id"]), user["email"])

    return {
        "message": "Registered successfully",
        "user": user,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/login")
def login_user(payload: LoginRequest):
    query = """
        SELECT id, name, email, created_at, password_hash
        FROM public.users
        WHERE email = %s;
    """

    try:
        _ensure_password_hash_column()
        with get_db_cursor() as cursor:
            cursor.execute(query, (payload.email,))
            user = cursor.fetchone()
    except Exception as exc:
        _raise_db_http_exception(exc)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.get("password_hash"):
        raise HTTPException(
            status_code=400,
            detail="User has no password set. Re-register this account.",
        )

    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    safe_user = {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "created_at": user["created_at"],
    }

    access_token = create_access_token(str(user["id"]), user["email"])
    refresh_token = create_refresh_token(str(user["id"]), user["email"])

    return {
        "message": "Login successful",
        "user": safe_user,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/google")
def google_login(payload: GoogleLoginRequest):
    try:
        _ensure_password_hash_column()
        _ensure_google_auth_columns()
        token_payload = google_id_token.verify_oauth2_token(
            payload.id_token,
            google_requests.Request(),
            _google_client_id(),
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    issuer = token_payload.get("iss")
    if issuer not in {"accounts.google.com", "https://accounts.google.com"}:
        raise HTTPException(status_code=401, detail="Invalid Google token issuer")

    if not token_payload.get("email_verified"):
        raise HTTPException(status_code=401, detail="Google email is not verified")

    google_sub = token_payload.get("sub")
    email = token_payload.get("email")
    name = token_payload.get("name")

    if not google_sub or not email:
        raise HTTPException(status_code=401, detail="Invalid Google token payload")

    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, email, created_at
                FROM public.users
                WHERE google_sub = %s OR email = %s
                ORDER BY created_at ASC
                LIMIT 1;
                """,
                (google_sub, email),
            )
            user = cursor.fetchone()

            if user:
                cursor.execute(
                    """
                    UPDATE public.users
                    SET
                        name = COALESCE(%s, name),
                        google_sub = COALESCE(google_sub, %s),
                        auth_provider = 'google'
                    WHERE id = %s
                    RETURNING id, name, email, created_at;
                    """,
                    (name, google_sub, user["id"]),
                )
                user = cursor.fetchone()
            else:
                cursor.execute(
                    """
                    INSERT INTO public.users (name, email, password_hash, google_sub, auth_provider)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, name, email, created_at;
                    """,
                    (name, email, None, google_sub, "google"),
                )
                user = cursor.fetchone()
    except Exception as exc:
        _raise_db_http_exception(exc)

    access_token = create_access_token(str(user["id"]), user["email"])
    refresh_token = create_refresh_token(str(user["id"]), user["email"])

    return {
        "message": "Google login successful",
        "user": user,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.get("/me")
def current_user(token_user=Depends(_token_user)):
    query = """
        SELECT id, name, email, created_at
        FROM public.users
        WHERE id = %s;
    """

    try:
        with get_db_cursor() as cursor:
            cursor.execute(query, (token_user["user_id"],))
            user = cursor.fetchone()
    except Exception as exc:
        _raise_db_http_exception(exc)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"user": user}


@router.post("/refresh")
def refresh_access_token(payload: RefreshRequest):
    try:
        token_payload = decode_token(payload.refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if token_payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = token_payload.get("sub")
    email = token_payload.get("email")
    if not user_id or not email:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    query = """
        SELECT id, email
        FROM public.users
        WHERE id = %s;
    """

    try:
        with get_db_cursor() as cursor:
            cursor.execute(query, (user_id,))
            user = cursor.fetchone()
    except Exception as exc:
        _raise_db_http_exception(exc)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    access_token = create_access_token(str(user["id"]), user["email"])
    refresh_token = create_refresh_token(str(user["id"]), user["email"])

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }
