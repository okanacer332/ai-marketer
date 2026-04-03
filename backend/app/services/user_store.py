from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from .database import get_database, normalize_email, utc_now


if TYPE_CHECKING:
    from .auth import AuthenticatedUser


USER_COLLECTION_NAME = "users"


def get_users_collection():
    return get_database()[USER_COLLECTION_NAME]


def ensure_user_indexes() -> None:
    users_collection = get_users_collection()

    users_collection.create_index(
        [("firebaseUid", ASCENDING)],
        unique=True,
        name="users_firebase_uid_unique",
    )
    users_collection.create_index(
        [("emailNormalized", ASCENDING)],
        unique=True,
        sparse=True,
        name="users_email_normalized_unique",
    )
    users_collection.create_index(
        [("defaultWorkspaceId", ASCENDING)],
        sparse=True,
        name="users_default_workspace_id",
    )
    users_collection.create_index(
        [("updatedAt", DESCENDING)],
        name="users_updated_at_desc",
    )


def get_user_by_firebase_uid(firebase_uid: str) -> dict[str, Any] | None:
    if not firebase_uid:
        return None

    return get_users_collection().find_one({"firebaseUid": firebase_uid})


def get_user_by_email(email: str | None) -> dict[str, Any] | None:
    normalized_email = normalize_email(email)
    if not normalized_email:
        return None

    return get_users_collection().find_one({"emailNormalized": normalized_email})


def get_user_by_identity(firebase_uid: str, email: str | None = None) -> dict[str, Any] | None:
    return get_user_by_firebase_uid(firebase_uid) or get_user_by_email(email)


def set_default_workspace(user_id: ObjectId, workspace_id: ObjectId) -> None:
    get_users_collection().update_one(
        {"_id": user_id},
        {
            "$set": {
                "defaultWorkspaceId": workspace_id,
                "updatedAt": utc_now(),
            }
        },
    )


def upsert_authenticated_user(user: AuthenticatedUser) -> None:
    users_collection = get_users_collection()
    now = utc_now()
    normalized_email = normalize_email(user.email)
    existing = users_collection.find_one(
        {"firebaseUid": user.uid},
        {
            "createdAt": 1,
            "displayName": 1,
            "photoUrl": 1,
            "providers": 1,
            "defaultWorkspaceId": 1,
        },
    )

    existing_providers = existing.get("providers", []) if isinstance(existing, dict) else []
    merged_providers = sorted(
        {
            provider.strip()
            for provider in [*existing_providers, *user.providers]
            if isinstance(provider, str) and provider.strip()
        }
    )

    users_collection.update_one(
        {"firebaseUid": user.uid},
        {
            "$set": {
                "firebaseUid": user.uid,
                "emailNormalized": normalized_email,
                "email": user.email,
                "displayName": user.display_name or (existing.get("displayName") if isinstance(existing, dict) else None),
                "photoUrl": user.photo_url or (existing.get("photoUrl") if isinstance(existing, dict) else None),
                "providers": merged_providers,
                "emailVerified": user.email_verified,
                "lastLoginAt": now,
                "updatedAt": now,
            },
            "$setOnInsert": {
                "createdAt": now,
                "defaultWorkspaceId": None,
            },
        },
        upsert=True,
    )
