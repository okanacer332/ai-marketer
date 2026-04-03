from __future__ import annotations

from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from .database import get_database, normalize_email, utc_now


SCHEMA_VERSION = 7
AUDIT_EVENT_COLLECTION_NAME = "audit_events"


def get_audit_events_collection():
    return get_database()[AUDIT_EVENT_COLLECTION_NAME]


def ensure_audit_indexes() -> None:
    collection = get_audit_events_collection()
    collection.create_index(
        [("workspaceId", ASCENDING), ("createdAt", DESCENDING)],
        name="audit_events_workspace_created_at",
    )
    collection.create_index(
        [("actorUserId", ASCENDING), ("createdAt", DESCENDING)],
        name="audit_events_user_created_at",
    )
    collection.create_index(
        [("eventType", ASCENDING), ("createdAt", DESCENDING)],
        name="audit_events_event_type_created_at",
    )
    collection.create_index(
        [("requestId", ASCENDING), ("createdAt", DESCENDING)],
        sparse=True,
        name="audit_events_request_id_created_at",
    )


def write_audit_event(
    *,
    event_type: str,
    status: str,
    entity_type: str,
    entity_id: ObjectId | str | None = None,
    user_document: dict[str, Any] | None = None,
    workspace_document: dict[str, Any] | None = None,
    website_document: dict[str, Any] | None = None,
    analysis_run_id: ObjectId | str | None = None,
    crawl_run_id: ObjectId | str | None = None,
    thread_id: ObjectId | str | None = None,
    request_id: str | None = None,
    payload: dict[str, Any] | None = None,
    now=None,
) -> ObjectId:
    event_time = now or utc_now()
    actor_user_id = user_document.get("_id") if isinstance(user_document, dict) else None
    actor_firebase_uid = (
        user_document.get("firebaseUid")
        if isinstance(user_document, dict) and isinstance(user_document.get("firebaseUid"), str)
        else None
    )
    actor_email_normalized = normalize_email(
        user_document.get("email")
        if isinstance(user_document, dict) and isinstance(user_document.get("email"), str)
        else user_document.get("emailNormalized")
        if isinstance(user_document, dict)
        else None
    )
    workspace_id = workspace_document.get("_id") if isinstance(workspace_document, dict) else None
    website_id = website_document.get("_id") if isinstance(website_document, dict) else None

    document = {
        "schemaVersion": SCHEMA_VERSION,
        "eventType": event_type,
        "status": status,
        "entityType": entity_type,
        "entityId": normalize_object_id(entity_id),
        "actorUserId": normalize_object_id(actor_user_id),
        "actorFirebaseUid": actor_firebase_uid,
        "actorEmailNormalized": actor_email_normalized,
        "workspaceId": normalize_object_id(workspace_id),
        "websiteId": normalize_object_id(website_id),
        "analysisRunId": normalize_object_id(analysis_run_id),
        "crawlRunId": normalize_object_id(crawl_run_id),
        "threadId": normalize_object_id(thread_id),
        "requestId": request_id.strip() if isinstance(request_id, str) and request_id.strip() else None,
        "payload": sanitize_payload(payload or {}),
        "createdAt": event_time,
    }
    result = get_audit_events_collection().insert_one(document)
    return result.inserted_id


def list_recent_audit_events(
    *,
    workspace_id: ObjectId | None = None,
    user_id: ObjectId | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if isinstance(workspace_id, ObjectId):
        query["workspaceId"] = workspace_id
    elif isinstance(user_id, ObjectId):
        query["actorUserId"] = user_id

    cursor = get_audit_events_collection().find(
        query,
        sort=[("createdAt", DESCENDING)],
    )
    if limit > 0:
        cursor = cursor.limit(limit)
    return list(cursor)


def serialize_audit_event(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(document.get("_id", "")),
        "eventType": get_non_empty_string(document.get("eventType")),
        "status": get_non_empty_string(document.get("status")) or "info",
        "entityType": get_non_empty_string(document.get("entityType")),
        "entityId": str(document.get("entityId")) if document.get("entityId") else None,
        "workspaceId": str(document.get("workspaceId")) if document.get("workspaceId") else None,
        "websiteId": str(document.get("websiteId")) if document.get("websiteId") else None,
        "userId": str(document.get("actorUserId")) if document.get("actorUserId") else None,
        "requestId": get_non_empty_string(document.get("requestId")) or None,
        "payload": sanitize_payload(document.get("payload", {})),
        "createdAt": document.get("createdAt").isoformat() if document.get("createdAt") else None,
    }


def normalize_object_id(value: ObjectId | str | None) -> ObjectId | None:
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if ObjectId.is_valid(stripped):
            return ObjectId(stripped)
    return None


def sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                continue
            result[key] = sanitize_payload(item)
        return result
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value[:64]]
    if isinstance(value, ObjectId):
        return str(value)
    if hasattr(value, "isoformat") and callable(value.isoformat):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def get_non_empty_string(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""
