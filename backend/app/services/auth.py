from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token as google_id_token

from .user_store import upsert_authenticated_user


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class AuthenticatedUser:
    uid: str
    email: str | None
    email_verified: bool
    display_name: str | None
    photo_url: str | None
    providers: list[str]
    raw_claims: dict[str, Any]


def get_firebase_project_id() -> str:
    return os.getenv("FIREBASE_PROJECT_ID", "").strip()


@lru_cache(maxsize=1)
def get_google_request() -> GoogleRequest:
    return GoogleRequest()


def extract_providers(claims: dict[str, Any]) -> list[str]:
    providers: list[str] = []
    firebase_payload = claims.get("firebase")

    if not isinstance(firebase_payload, dict):
        return providers

    sign_in_provider = firebase_payload.get("sign_in_provider")
    if isinstance(sign_in_provider, str) and sign_in_provider.strip():
        providers.append(sign_in_provider.strip())

    identities = firebase_payload.get("identities")
    if isinstance(identities, dict):
        for provider_name in identities.keys():
            if isinstance(provider_name, str) and provider_name.strip():
                providers.append(provider_name.strip())

    return sorted(set(providers))


def build_authenticated_user(claims: dict[str, Any]) -> AuthenticatedUser:
    uid = str(claims.get("user_id") or claims.get("uid") or claims.get("sub") or "").strip()
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz oturum bilgisi.",
        )

    email = claims.get("email")
    display_name = claims.get("name")
    photo_url = claims.get("picture")

    return AuthenticatedUser(
        uid=uid,
        email=email.strip() if isinstance(email, str) and email.strip() else None,
        email_verified=bool(claims.get("email_verified", False)),
        display_name=display_name.strip() if isinstance(display_name, str) and display_name.strip() else None,
        photo_url=photo_url.strip() if isinstance(photo_url, str) and photo_url.strip() else None,
        providers=extract_providers(claims),
        raw_claims=claims,
    )


def read_bearer_token(credentials: HTTPAuthorizationCredentials | None) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Oturum doğrulaması gerekiyor.",
        )

    token = credentials.credentials.strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Oturum doğrulaması gerekiyor.",
        )

    return token


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser:
    project_id = get_firebase_project_id()
    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Firebase proje kimliği yapılandırılmadı.",
        )

    token = read_bearer_token(credentials)

    try:
        claims = google_id_token.verify_firebase_token(
            token,
            get_google_request(),
            project_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Oturum doğrulanamadı.",
        ) from exc
    except Exception as exc:  # pragma: no cover - network/certificate path
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Kimlik doğrulama servisine şu anda ulaşılamıyor.",
        ) from exc

    if not isinstance(claims, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Oturum doğrulanamadı.",
        )

    user = build_authenticated_user(claims)
    upsert_authenticated_user(user)
    return user
