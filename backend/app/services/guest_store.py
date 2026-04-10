from __future__ import annotations

from uuid import uuid4

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from .database import get_database, utc_now
from .user_store import get_user_by_firebase_uid, get_users_collection, set_default_workspace
from .workspace_store import (
    ensure_workspace_membership,
    get_active_workspace_for_user,
    get_workspaces_collection,
)


GUEST_SESSION_COLLECTION_NAME = "guest_sessions"


def get_guest_sessions_collection():
    return get_database()[GUEST_SESSION_COLLECTION_NAME]


def ensure_guest_indexes() -> None:
    sessions = get_guest_sessions_collection()

    sessions.create_index(
        [("sessionId", ASCENDING)],
        unique=True,
        name="guest_sessions_session_id_unique",
    )
    sessions.create_index(
        [("guestFirebaseUid", ASCENDING)],
        unique=True,
        name="guest_sessions_guest_firebase_uid_unique",
    )
    sessions.create_index(
        [("status", ASCENDING), ("updatedAt", DESCENDING)],
        name="guest_sessions_status_updated_at",
    )


def build_guest_firebase_uid(session_id: str) -> str:
    return f"guest:{session_id}"


def create_guest_session() -> dict:
    session_id = uuid4().hex
    return ensure_guest_session(session_id)


def ensure_guest_session(session_id: str) -> dict:
    cleaned_session_id = session_id.strip()
    if not cleaned_session_id:
        raise ValueError("Guest oturumu oluşturulamadı.")

    now = utc_now()
    guest_firebase_uid = build_guest_firebase_uid(cleaned_session_id)
    users = get_users_collection()

    users.update_one(
        {"firebaseUid": guest_firebase_uid},
        {
            "$set": {
                "firebaseUid": guest_firebase_uid,
                "displayName": "Misafir",
                "photoUrl": None,
                "providers": ["guest"],
                "emailVerified": False,
                "lastLoginAt": now,
                "updatedAt": now,
            },
            "$unset": {
                "emailNormalized": "",
                "email": "",
            },
            "$setOnInsert": {
                "createdAt": now,
                "defaultWorkspaceId": None,
            },
        },
        upsert=True,
    )

    guest_user = get_user_by_firebase_uid(guest_firebase_uid)
    if not guest_user:
        raise ValueError("Guest kullanıcı oluşturulamadı.")

    sessions = get_guest_sessions_collection()
    sessions.update_one(
        {"sessionId": cleaned_session_id},
        {
            "$set": {
                "sessionId": cleaned_session_id,
                "guestFirebaseUid": guest_firebase_uid,
                "guestUserId": guest_user["_id"],
                "status": "active",
                "updatedAt": now,
            },
            "$setOnInsert": {
                "createdAt": now,
                "claimedByUserId": None,
                "claimedAt": None,
                "workspaceId": None,
            },
        },
        upsert=True,
    )

    return sessions.find_one({"sessionId": cleaned_session_id}) or {
        "sessionId": cleaned_session_id,
        "guestFirebaseUid": guest_firebase_uid,
        "guestUserId": guest_user["_id"],
        "status": "active",
    }


def get_guest_session(session_id: str) -> dict | None:
    cleaned_session_id = session_id.strip()
    if not cleaned_session_id:
        return None

    return get_guest_sessions_collection().find_one({"sessionId": cleaned_session_id})


def get_guest_user_document(session_id: str) -> dict | None:
    session_document = get_guest_session(session_id)
    if not session_document:
        return None

    guest_firebase_uid = session_document.get("guestFirebaseUid")
    if not isinstance(guest_firebase_uid, str) or not guest_firebase_uid.strip():
        return None

    return get_user_by_firebase_uid(guest_firebase_uid)


def attach_workspace_to_guest_session(session_id: str, workspace_id: ObjectId | None) -> None:
    if not session_id.strip() or not isinstance(workspace_id, ObjectId):
        return

    get_guest_sessions_collection().update_one(
        {"sessionId": session_id.strip()},
        {
            "$set": {
                "workspaceId": workspace_id,
                "updatedAt": utc_now(),
            }
        },
    )


def claim_guest_session_to_user(
    session_id: str,
    authenticated_user_document: dict,
) -> ObjectId | None:
    session_document = get_guest_session(session_id)
    if not session_document:
        return None

    guest_user_document = get_guest_user_document(session_id)
    if not guest_user_document:
        return None

    guest_workspace = get_active_workspace_for_user(guest_user_document)
    if not guest_workspace:
        get_guest_sessions_collection().update_one(
            {"_id": session_document["_id"]},
            {
                "$set": {
                    "status": "claimed",
                    "claimedByUserId": authenticated_user_document["_id"],
                    "claimedAt": utc_now(),
                    "updatedAt": utc_now(),
                }
            },
        )
        return None

    now = utc_now()
    get_workspaces_collection().update_one(
        {"_id": guest_workspace["_id"]},
        {
            "$set": {
                "ownerUserId": authenticated_user_document["_id"],
                "ownerFirebaseUid": authenticated_user_document.get("firebaseUid"),
                "ownerEmailNormalized": authenticated_user_document.get("emailNormalized"),
                "updatedAt": now,
            }
        },
    )

    ensure_workspace_membership(guest_workspace["_id"], authenticated_user_document["_id"], now)
    set_default_workspace(authenticated_user_document["_id"], guest_workspace["_id"])

    get_guest_sessions_collection().update_one(
        {"_id": session_document["_id"]},
        {
            "$set": {
                "status": "claimed",
                "claimedByUserId": authenticated_user_document["_id"],
                "claimedAt": now,
                "workspaceId": guest_workspace["_id"],
                "updatedAt": now,
            }
        },
    )

    return guest_workspace["_id"]
