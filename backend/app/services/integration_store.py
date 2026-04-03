from __future__ import annotations

import re
from typing import Any, Iterable

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from .database import get_database


SCHEMA_VERSION = 6
INTEGRATION_CONNECTION_COLLECTION_NAME = "integration_connections"
INTEGRATION_SYNC_RUN_COLLECTION_NAME = "integration_sync_runs"
PENDING_CONNECTION_MESSAGE = (
    "OAuth bağlantısı henüz kurulmadı. Seçim kaydedildi, senkron başlatılmadı."
)
REMOVED_CONNECTION_MESSAGE = (
    "Platform seçimden çıkarıldı. Otomatik senkron bu workspace için durduruldu."
)
KNOWN_PROVIDERS = {
    "google-analytics": {
        "provider": "Google Analytics",
        "aliases": [
            "google analytics",
            "google-analytics",
            "googleanalytics",
            "ga4",
        ],
    },
    "meta-ads": {
        "provider": "Meta Ads",
        "aliases": [
            "meta ads",
            "meta-ads",
            "facebook ads",
            "facebook-ads",
            "metaads",
        ],
    },
    "instagram": {
        "provider": "Instagram",
        "aliases": ["instagram", "instagram business"],
    },
    "shopify-or-ticimax": {
        "provider": "Shopify veya Ticimax",
        "aliases": [
            "shopify",
            "ticimax",
            "shopify veya ticimax",
            "shopify or ticimax",
            "shopify-ticimax",
        ],
    },
}


def get_integration_connections_collection():
    return get_database()[INTEGRATION_CONNECTION_COLLECTION_NAME]


def get_integration_sync_runs_collection():
    return get_database()[INTEGRATION_SYNC_RUN_COLLECTION_NAME]


def ensure_integration_indexes() -> None:
    connections = get_integration_connections_collection()
    sync_runs = get_integration_sync_runs_collection()

    connections.create_index(
        [("workspaceId", ASCENDING), ("providerKey", ASCENDING)],
        unique=True,
        name="integration_connections_workspace_provider_unique",
    )
    connections.create_index(
        [("workspaceId", ASCENDING), ("status", ASCENDING), ("updatedAt", DESCENDING)],
        name="integration_connections_workspace_status_updated_at",
    )
    connections.create_index(
        [("lastSyncRunId", ASCENDING)],
        sparse=True,
        name="integration_connections_last_sync_run_id",
    )
    connections.create_index(
        [("updatedAt", DESCENDING)],
        name="integration_connections_updated_at",
    )

    sync_runs.create_index(
        [("workspaceId", ASCENDING), ("createdAt", DESCENDING)],
        name="integration_sync_runs_workspace_created_at",
    )
    sync_runs.create_index(
        [("connectionId", ASCENDING), ("createdAt", DESCENDING)],
        name="integration_sync_runs_connection_created_at",
    )
    sync_runs.create_index(
        [("providerKey", ASCENDING), ("createdAt", DESCENDING)],
        name="integration_sync_runs_provider_created_at",
    )
    sync_runs.create_index(
        [("status", ASCENDING), ("createdAt", DESCENDING)],
        name="integration_sync_runs_status_created_at",
    )


def sync_workspace_integrations(
    workspace_document: dict[str, Any],
    selected_platforms: list[str] | None,
    now,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected_providers = normalize_selected_providers(selected_platforms)
    selected_keys = {provider["providerKey"] for provider in selected_providers}
    workspace_id = workspace_document["_id"]
    connections = get_integration_connections_collection()
    existing_documents = list(connections.find({"workspaceId": workspace_id}))
    existing_by_key = {
        get_non_empty_string(document.get("providerKey")): document
        for document in existing_documents
        if get_non_empty_string(document.get("providerKey"))
    }

    for provider in selected_providers:
        existing_document = existing_by_key.get(provider["providerKey"])
        if existing_document:
            connection_id = existing_document["_id"]
            updates = {
                "schemaVersion": SCHEMA_VERSION,
                "provider": provider["provider"],
                "selectedViaOnboarding": True,
                "updatedAt": now,
            }
            should_log_selection = False

            if get_non_empty_string(existing_document.get("status")) in {"", "not_connected", "disconnected"}:
                updates.update(
                    {
                        "status": "pending",
                        "authMode": "selection_only",
                        "accountLabel": "Bağlantı bekleniyor",
                        "errorMessage": None,
                    }
                )
                should_log_selection = True

            connections.update_one({"_id": connection_id}, {"$set": updates})

            if should_log_selection:
                record_integration_sync_run(
                    connection_id=connection_id,
                    workspace_id=workspace_id,
                    provider_key=provider["providerKey"],
                    provider_name=provider["provider"],
                    status="skipped",
                    trigger="workspace_selection",
                    message=PENDING_CONNECTION_MESSAGE,
                    now=now,
                    result_summary={
                        "selectionMode": "selection_only",
                        "reason": "oauth_not_connected",
                    },
                )
            continue

        document = {
            "schemaVersion": SCHEMA_VERSION,
            "workspaceId": workspace_id,
            "providerKey": provider["providerKey"],
            "provider": provider["provider"],
            "status": "pending",
            "accountLabel": "Bağlantı bekleniyor",
            "scopes": [],
            "tokenRef": None,
            "authMode": "selection_only",
            "selectedViaOnboarding": True,
            "lastSyncRunId": None,
            "lastSyncStatus": None,
            "lastSyncMessage": None,
            "lastSyncAt": None,
            "errorMessage": None,
            "createdAt": now,
            "updatedAt": now,
        }
        insert_result = connections.insert_one(document)
        record_integration_sync_run(
            connection_id=insert_result.inserted_id,
            workspace_id=workspace_id,
            provider_key=provider["providerKey"],
            provider_name=provider["provider"],
            status="skipped",
            trigger="workspace_selection",
            message=PENDING_CONNECTION_MESSAGE,
            now=now,
            result_summary={
                "selectionMode": "selection_only",
                "reason": "oauth_not_connected",
            },
        )

    for existing_document in existing_documents:
        provider_key = get_non_empty_string(existing_document.get("providerKey"))
        if not provider_key or provider_key in selected_keys:
            continue
        if get_non_empty_string(existing_document.get("status")) == "not_connected":
            continue

        get_integration_connections_collection().update_one(
            {"_id": existing_document["_id"]},
            {
                "$set": {
                    "schemaVersion": SCHEMA_VERSION,
                    "status": "not_connected",
                    "selectedViaOnboarding": False,
                    "authMode": "selection_only",
                    "errorMessage": None,
                    "updatedAt": now,
                }
            },
        )
        record_integration_sync_run(
            connection_id=existing_document["_id"],
            workspace_id=workspace_id,
            provider_key=provider_key,
            provider_name=get_non_empty_string(existing_document.get("provider")) or provider_key,
            status="skipped",
            trigger="workspace_selection",
            message=REMOVED_CONNECTION_MESSAGE,
            now=now,
            result_summary={
                "selectionMode": "removed",
                "reason": "provider_unselected",
            },
        )

    return (
        get_integration_connections_for_workspace(workspace_document, include_inactive=False),
        get_recent_integration_sync_runs_for_workspace(workspace_document),
    )


def get_integration_connections_for_workspace(
    workspace_document: dict[str, Any],
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"workspaceId": workspace_document["_id"]}
    if not include_inactive:
        query["status"] = {"$ne": "not_connected"}

    documents = list(
        get_integration_connections_collection().find(
            query,
            sort=[("status", ASCENDING), ("provider", ASCENDING), ("updatedAt", DESCENDING)],
        )
    )
    return documents


def get_recent_integration_sync_runs_for_workspace(
    workspace_document: dict[str, Any],
    limit: int = 6,
) -> list[dict[str, Any]]:
    cursor = get_integration_sync_runs_collection().find(
        {"workspaceId": workspace_document["_id"]},
        sort=[("createdAt", DESCENDING)],
    )
    if limit > 0:
        cursor = cursor.limit(limit)
    return list(cursor)


def enrich_analysis_result_with_integrations(
    analysis_result: dict[str, Any] | None,
    integration_connections: list[dict[str, Any]] | None,
    integration_sync_runs: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    result = repair_value(analysis_result or {})
    result["integrationConnections"] = [
        serialize_integration_connection(document)
        for document in integration_connections or []
    ]
    result["integrationSyncRuns"] = [
        serialize_integration_sync_run(document)
        for document in integration_sync_runs or []
    ]
    return result


def strip_integration_payload(analysis_result: dict[str, Any] | None) -> dict[str, Any]:
    cleaned_result = repair_value(analysis_result or {})
    if isinstance(cleaned_result, dict):
        cleaned_result.pop("integrationConnections", None)
        cleaned_result.pop("integrationSyncRuns", None)
    return cleaned_result


def build_preview_integration_payload(selected_platforms: list[str] | None) -> dict[str, list[dict[str, Any]]]:
    providers = normalize_selected_providers(selected_platforms)
    return {
        "integrationConnections": [
            {
                "id": f"preview-{provider['providerKey']}",
                "providerKey": provider["providerKey"],
                "provider": provider["provider"],
                "status": "pending",
                "accountLabel": "Bağlantı bekleniyor",
                "scopes": [],
                "authMode": "selection_only",
                "tokenConfigured": False,
                "lastSyncStatus": "skipped",
                "lastSyncMessage": PENDING_CONNECTION_MESSAGE,
                "lastSyncAt": None,
                "updatedAt": None,
            }
            for provider in providers
        ],
        "integrationSyncRuns": [
            {
                "id": f"preview-sync-{provider['providerKey']}",
                "providerKey": provider["providerKey"],
                "provider": provider["provider"],
                "status": "skipped",
                "trigger": "workspace_selection",
                "message": PENDING_CONNECTION_MESSAGE,
                "startedAt": None,
                "finishedAt": None,
            }
            for provider in providers
        ],
    }


def record_integration_sync_run(
    connection_id: ObjectId,
    workspace_id: ObjectId,
    provider_key: str,
    provider_name: str,
    status: str,
    trigger: str,
    message: str,
    now,
    result_summary: dict[str, Any] | None = None,
) -> ObjectId:
    document = {
        "schemaVersion": SCHEMA_VERSION,
        "workspaceId": workspace_id,
        "connectionId": connection_id,
        "providerKey": provider_key,
        "provider": provider_name,
        "status": status,
        "trigger": trigger,
        "message": message,
        "resultSummary": repair_value(result_summary or {}),
        "startedAt": now,
        "finishedAt": now,
        "createdAt": now,
    }
    insert_result = get_integration_sync_runs_collection().insert_one(document)
    get_integration_connections_collection().update_one(
        {"_id": connection_id},
        {
            "$set": {
                "lastSyncRunId": insert_result.inserted_id,
                "lastSyncStatus": status,
                "lastSyncMessage": message,
                "lastSyncAt": now,
                "updatedAt": now,
            }
        },
    )
    return insert_result.inserted_id


def serialize_integration_connection(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(document.get("_id", "")),
        "providerKey": get_non_empty_string(document.get("providerKey")),
        "provider": get_non_empty_string(document.get("provider")),
        "status": get_non_empty_string(document.get("status")) or "pending",
        "accountLabel": get_non_empty_string(document.get("accountLabel")),
        "scopes": normalize_string_list(document.get("scopes")),
        "authMode": get_non_empty_string(document.get("authMode")) or "selection_only",
        "tokenConfigured": bool(document.get("tokenRef")),
        "lastSyncStatus": get_non_empty_string(document.get("lastSyncStatus")),
        "lastSyncMessage": get_non_empty_string(document.get("lastSyncMessage")),
        "lastSyncAt": document.get("lastSyncAt").isoformat() if document.get("lastSyncAt") else None,
        "updatedAt": document.get("updatedAt").isoformat() if document.get("updatedAt") else None,
    }


def serialize_integration_sync_run(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(document.get("_id", "")),
        "providerKey": get_non_empty_string(document.get("providerKey")),
        "provider": get_non_empty_string(document.get("provider")),
        "status": get_non_empty_string(document.get("status")) or "queued",
        "trigger": get_non_empty_string(document.get("trigger")) or "workspace_selection",
        "message": get_non_empty_string(document.get("message")),
        "startedAt": document.get("startedAt").isoformat() if document.get("startedAt") else None,
        "finishedAt": document.get("finishedAt").isoformat() if document.get("finishedAt") else None,
    }


def normalize_selected_providers(value: list[str] | None) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in value:
        label = get_non_empty_string(item)
        if not label:
            continue
        provider_key, provider_name = resolve_provider_identity(label)
        if provider_key in seen:
            continue
        seen.add(provider_key)
        normalized.append(
            {
                "providerKey": provider_key,
                "provider": provider_name,
            }
        )
    return normalized


def resolve_provider_identity(label: str) -> tuple[str, str]:
    normalized_label = slugify(label)
    for provider_key, config in KNOWN_PROVIDERS.items():
        aliases = [slugify(alias) for alias in config.get("aliases", [])]
        if normalized_label in aliases:
            return provider_key, config["provider"]

    if "google" in normalized_label and "analytics" in normalized_label:
        return "google-analytics", KNOWN_PROVIDERS["google-analytics"]["provider"]
    if "meta" in normalized_label and "ads" in normalized_label:
        return "meta-ads", KNOWN_PROVIDERS["meta-ads"]["provider"]
    if "instagram" in normalized_label:
        return "instagram", KNOWN_PROVIDERS["instagram"]["provider"]
    if "shopify" in normalized_label or "ticimax" in normalized_label:
        return "shopify-or-ticimax", KNOWN_PROVIDERS["shopify-or-ticimax"]["provider"]

    return normalized_label or "custom-platform", label.strip()


def normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def get_non_empty_string(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


def repair_value(value: Any) -> Any:
    if isinstance(value, str):
        return repair_text(value)
    if isinstance(value, list):
        return [repair_value(item) for item in value]
    if isinstance(value, dict):
        return {key: repair_value(item) for key, item in value.items() if key != "_id"}
    return value


def repair_text(value: str) -> str:
    if not any(
        marker in value
        for marker in (
            "ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢",
            "ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦",
            "ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â",
            "ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢",
        )
    ):
        return value
    try:
        return value.encode("latin1").decode("utf-8")
    except Exception:
        return value
