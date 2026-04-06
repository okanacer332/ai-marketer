from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from .chat_store import (
    create_or_update_analysis_thread,
    enrich_analysis_result_with_chat_thread,
    ensure_chat_indexes,
    get_latest_thread_for_workspace,
    get_messages_for_thread,
)
from .audit_store import ensure_audit_indexes
from .crawl_store import (
    create_crawl_records,
    enrich_analysis_result_with_crawl_data,
    ensure_crawl_indexes,
    get_crawled_pages_for_run,
    get_latest_crawl_run_for_workspace,
    strip_crawl_payload,
)
from .integration_store import (
    enrich_analysis_result_with_integrations,
    ensure_integration_indexes,
    get_integration_connections_for_workspace,
    get_recent_integration_sync_runs_for_workspace,
    strip_integration_payload,
    sync_workspace_integrations,
)
from .database import get_database, normalize_email, utc_now
from .memory_store import (
    create_or_reuse_memory_documents,
    enrich_analysis_result_with_memory_files,
    ensure_memory_indexes,
    get_memory_documents_for_analysis_run,
    strip_memory_payload,
)
from .user_store import get_user_by_identity, set_default_workspace


SCHEMA_VERSION = 7
WORKSPACE_COLLECTION_NAME = "workspaces"
WORKSPACE_MEMBER_COLLECTION_NAME = "workspace_members"
WEBSITE_COLLECTION_NAME = "websites"
ANALYSIS_RUN_COLLECTION_NAME = "analysis_runs"
LEGACY_WORKSPACE_COLLECTION_NAME = "workspace_snapshots"


def get_workspaces_collection():
    return get_database()[WORKSPACE_COLLECTION_NAME]


def get_workspace_members_collection():
    return get_database()[WORKSPACE_MEMBER_COLLECTION_NAME]


def get_websites_collection():
    return get_database()[WEBSITE_COLLECTION_NAME]


def get_analysis_runs_collection():
    return get_database()[ANALYSIS_RUN_COLLECTION_NAME]


def get_legacy_workspace_collection():
    return get_database()[LEGACY_WORKSPACE_COLLECTION_NAME]


def ensure_indexes() -> None:
    workspaces_collection = get_workspaces_collection()
    workspace_members_collection = get_workspace_members_collection()
    websites_collection = get_websites_collection()
    analysis_runs_collection = get_analysis_runs_collection()

    ensure_chat_indexes()
    ensure_crawl_indexes()
    ensure_integration_indexes()
    ensure_memory_indexes()
    ensure_audit_indexes()

    workspaces_collection.create_index(
        [("ownerUserId", ASCENDING), ("updatedAt", DESCENDING)],
        name="workspaces_owner_updated_at",
    )
    workspaces_collection.create_index(
        [("ownerFirebaseUid", ASCENDING), ("updatedAt", DESCENDING)],
        name="workspaces_owner_firebase_uid_updated_at",
    )
    workspaces_collection.create_index(
        [("slug", ASCENDING)],
        unique=True,
        name="workspaces_slug_unique",
    )
    workspaces_collection.create_index(
        [("currentWebsiteId", ASCENDING)],
        sparse=True,
        name="workspaces_current_website_id",
    )
    workspaces_collection.create_index(
        [("latestAnalysisRunId", ASCENDING)],
        sparse=True,
        name="workspaces_latest_analysis_run_id",
    )
    workspaces_collection.create_index(
        [("latestCrawlRunId", ASCENDING)],
        sparse=True,
        name="workspaces_latest_crawl_run_id",
    )
    workspaces_collection.create_index(
        [("latestThreadId", ASCENDING)],
        sparse=True,
        name="workspaces_latest_thread_id",
    )

    workspace_members_collection.create_index(
        [("workspaceId", ASCENDING), ("userId", ASCENDING)],
        unique=True,
        name="workspace_members_workspace_user_unique",
    )
    workspace_members_collection.create_index(
        [("userId", ASCENDING), ("status", ASCENDING)],
        name="workspace_members_user_status",
    )

    websites_collection.create_index(
        [("workspaceId", ASCENDING), ("domain", ASCENDING)],
        unique=True,
        sparse=True,
        name="websites_workspace_domain_unique",
    )
    websites_collection.create_index(
        [("workspaceId", ASCENDING), ("updatedAt", DESCENDING)],
        name="websites_workspace_updated_at",
    )
    websites_collection.create_index(
        [("lastAnalysisRunId", ASCENDING)],
        sparse=True,
        name="websites_last_analysis_run_id",
    )
    websites_collection.create_index(
        [("lastCrawlRunId", ASCENDING)],
        sparse=True,
        name="websites_last_crawl_run_id",
    )

    drop_conflicting_index(analysis_runs_collection, "analysis_runs_user_created_at")

    analysis_runs_collection.create_index(
        [("workspaceId", ASCENDING), ("createdAt", DESCENDING)],
        name="analysis_runs_workspace_created_at",
    )
    analysis_runs_collection.create_index(
        [("websiteId", ASCENDING), ("createdAt", DESCENDING)],
        name="analysis_runs_website_created_at",
    )
    analysis_runs_collection.create_index(
        [("triggeredByUserId", ASCENDING), ("createdAt", DESCENDING)],
        name="analysis_runs_user_created_at",
    )
    analysis_runs_collection.create_index(
        [("analysisFingerprint", ASCENDING)],
        name="analysis_runs_fingerprint",
    )
    analysis_runs_collection.create_index(
        [("crawlRunId", ASCENDING)],
        sparse=True,
        name="analysis_runs_crawl_run_id",
    )

def drop_conflicting_index(collection, index_name: str) -> None:
    try:
        existing_indexes = collection.index_information()
        if index_name in existing_indexes:
            collection.drop_index(index_name)
    except Exception:
        # Existing deployments may not have the index or may be concurrently rebuilding it.
        pass


def ping_database() -> bool:
    try:
        get_database().command("ping")
        return True
    except Exception:
        return False


def save_workspace_snapshot(
    user_id: str,
    email: str | None,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    user_document = get_user_by_identity(user_id, email)
    if not user_document:
        raise ValueError("Doğrulanmış kullanıcı bulunamadı.")

    cleaned_snapshot = repair_value(snapshot)
    normalized_email = normalize_email(email)
    now = utc_now()
    website = str(cleaned_snapshot.get("website", "")).strip()
    analysis_result = cleaned_snapshot.get("analysisResult", {}) or {}
    analysis = analysis_result.get("analysis", {}) if isinstance(analysis_result, dict) else {}
    website_domain = infer_website_domain(website, analysis)
    analysis_fingerprint = build_analysis_fingerprint(user_id, website, analysis_result)

    workspace_document = ensure_workspace_document(
        user_document=user_document,
        snapshot=cleaned_snapshot,
        website_domain=website_domain,
        now=now,
    )
    website_document = ensure_website_document(
        workspace_document=workspace_document,
        snapshot=cleaned_snapshot,
        website=website,
        website_domain=website_domain,
        now=now,
    )
    sync_workspace_integrations(
        workspace_document=workspace_document,
        selected_platforms=cleaned_snapshot.get("connectedPlatforms", [])
        if isinstance(cleaned_snapshot.get("connectedPlatforms"), list)
        else [],
        now=now,
    )
    crawl_run_id = create_crawl_records(
        workspace_document=workspace_document,
        website_document=website_document,
        user_document=user_document,
        analysis_result=analysis_result if isinstance(analysis_result, dict) else {},
        now=now,
    )

    analysis_run_id = create_analysis_run(
        workspace_document=workspace_document,
        website_document=website_document,
        user_document=user_document,
        normalized_email=normalized_email,
        snapshot=cleaned_snapshot,
        crawl_run_id=crawl_run_id,
        analysis_fingerprint=analysis_fingerprint,
        now=now,
    )
    memory_document_ids = create_or_reuse_memory_documents(
        workspace_document=workspace_document,
        website_document=website_document,
        analysis_run_id=analysis_run_id,
        analysis_result=analysis_result if isinstance(analysis_result, dict) else {},
        now=now,
    )
    if memory_document_ids:
        get_analysis_runs_collection().update_one(
            {"_id": analysis_run_id},
            {
                "$set": {
                    "memoryDocumentIds": memory_document_ids,
                    "analysisSummary.memoryFileCount": len(memory_document_ids),
                    "updatedAt": now,
                }
            },
        )
    analysis_run_document = get_analysis_runs_collection().find_one({"_id": analysis_run_id})
    memory_documents = get_memory_documents_for_analysis_run(analysis_run_document or {"_id": analysis_run_id})
    latest_thread_id = None
    if analysis_run_document:
        latest_thread_id = create_or_update_analysis_thread(
            workspace_document=workspace_document,
            user_document=user_document,
            analysis_run_document=analysis_run_document,
            memory_documents=memory_documents,
            analysis_result=analysis_result if isinstance(analysis_result, dict) else {},
            specialist_id=str(cleaned_snapshot.get("selectedSpecialist", "aylin")),
            now=now,
        )

    website_updates = {
        "lastAnalysisRunId": analysis_run_id,
        "lastAnalysisAt": now,
        "updatedAt": now,
    }
    if crawl_run_id:
        website_updates["lastCrawlRunId"] = crawl_run_id
        website_updates["lastCrawledAt"] = now

    get_websites_collection().update_one(
        {"_id": website_document["_id"]},
        {"$set": website_updates},
    )

    workspace_updates = {
        "schemaVersion": SCHEMA_VERSION,
        "name": build_workspace_name(cleaned_snapshot, user_document),
        "selectedSpecialist": cleaned_snapshot.get("selectedSpecialist", "aylin"),
        "status": "active",
        "trial": {
            "activated": bool(cleaned_snapshot.get("trialActivated", False)),
            "activatedAt": now if bool(cleaned_snapshot.get("trialActivated", False)) else None,
        },
        "currentState": {
            "website": website,
            "websiteDomain": website_domain,
            "selectedGoals": cleaned_snapshot.get("selectedGoals", [])
            if isinstance(cleaned_snapshot.get("selectedGoals"), list)
            else [],
            "connectedPlatforms": cleaned_snapshot.get("connectedPlatforms", [])
            if isinstance(cleaned_snapshot.get("connectedPlatforms"), list)
            else [],
        },
        "currentWebsiteId": website_document["_id"],
        "latestAnalysisRunId": analysis_run_id,
        "lastAnalysisAt": now,
        "updatedAt": now,
    }
    if crawl_run_id:
        workspace_updates["latestCrawlRunId"] = crawl_run_id
        workspace_updates["lastCrawledAt"] = now
    if latest_thread_id:
        workspace_updates["latestThreadId"] = latest_thread_id

    get_workspaces_collection().update_one(
        {"_id": workspace_document["_id"]},
        {"$set": workspace_updates},
    )
    return {
        "userDocument": user_document,
        "workspaceDocument": {
            "_id": workspace_document["_id"],
            "name": workspace_updates["name"],
        },
        "websiteDocument": {
            "_id": website_document["_id"],
            "domain": website_domain,
            "inputUrl": website,
        },
        "analysisRunId": analysis_run_id,
        "crawlRunId": crawl_run_id,
        "threadId": latest_thread_id,
    }


def get_workspace_snapshot(
    user_id: str,
    email: str | None = None,
) -> dict[str, Any] | None:
    user_document = get_user_by_identity(user_id, email)
    if not user_document:
        return None

    workspace_document = get_active_workspace_for_user(user_document)
    if not workspace_document:
        migrated_snapshot = migrate_legacy_snapshot_if_present(user_id, email)
        if migrated_snapshot:
            return migrated_snapshot
        return None

    analysis_run_document = get_latest_analysis_run_for_workspace(workspace_document)
    if not analysis_run_document:
        return None

    website_document = get_current_website_for_workspace(workspace_document)
    return build_workspace_snapshot_response(
        workspace_document=workspace_document,
        website_document=website_document,
        analysis_run_document=analysis_run_document,
    )


def get_active_workspace_context(
    user_id: str,
    email: str | None = None,
) -> dict[str, Any] | None:
    user_document = get_user_by_identity(user_id, email)
    if not user_document:
        return None

    workspace_document = get_active_workspace_for_user(user_document)
    if not workspace_document:
        return {
            "userDocument": user_document,
            "workspaceDocument": None,
            "websiteDocument": None,
            "analysisRunDocument": None,
        }

    website_document = get_current_website_for_workspace(workspace_document)
    analysis_run_document = get_latest_analysis_run_for_workspace(workspace_document)
    return {
        "userDocument": user_document,
        "workspaceDocument": workspace_document,
        "websiteDocument": website_document,
        "analysisRunDocument": analysis_run_document,
    }


def ensure_workspace_document(
    user_document: dict[str, Any],
    snapshot: dict[str, Any],
    website_domain: str,
    now,
) -> dict[str, Any]:
    workspaces_collection = get_workspaces_collection()
    workspace_document = get_active_workspace_for_user(user_document)
    workspace_name = build_workspace_name(snapshot, user_document)

    if workspace_document:
        workspaces_collection.update_one(
            {"_id": workspace_document["_id"]},
            {
                "$set": {
                    "schemaVersion": SCHEMA_VERSION,
                    "name": workspace_name,
                    "selectedSpecialist": snapshot.get("selectedSpecialist", "aylin"),
                    "status": "active",
                    "updatedAt": now,
                    "currentState": {
                        "website": str(snapshot.get("website", "")).strip(),
                        "websiteDomain": website_domain,
                        "selectedGoals": snapshot.get("selectedGoals", [])
                        if isinstance(snapshot.get("selectedGoals"), list)
                        else [],
                        "connectedPlatforms": snapshot.get("connectedPlatforms", [])
                        if isinstance(snapshot.get("connectedPlatforms"), list)
                        else [],
                    },
                }
            },
        )
        workspace_document = workspaces_collection.find_one({"_id": workspace_document["_id"]})
        if workspace_document:
            return workspace_document

    slug = build_workspace_slug(workspace_name, str(user_document.get("firebaseUid", "")))
    workspace_document = {
        "schemaVersion": SCHEMA_VERSION,
        "ownerUserId": user_document["_id"],
        "ownerFirebaseUid": user_document.get("firebaseUid"),
        "ownerEmailNormalized": user_document.get("emailNormalized"),
        "name": workspace_name,
        "slug": slug,
        "status": "active",
        "selectedSpecialist": snapshot.get("selectedSpecialist", "aylin"),
        "trial": {
            "activated": bool(snapshot.get("trialActivated", False)),
            "activatedAt": now if bool(snapshot.get("trialActivated", False)) else None,
        },
        "currentState": {
            "website": str(snapshot.get("website", "")).strip(),
            "websiteDomain": website_domain,
            "selectedGoals": snapshot.get("selectedGoals", [])
            if isinstance(snapshot.get("selectedGoals"), list)
            else [],
            "connectedPlatforms": snapshot.get("connectedPlatforms", [])
            if isinstance(snapshot.get("connectedPlatforms"), list)
            else [],
        },
        "currentWebsiteId": None,
        "latestCrawlRunId": None,
        "latestAnalysisRunId": None,
        "latestThreadId": None,
        "lastCrawledAt": None,
        "lastAnalysisAt": now,
        "createdAt": now,
        "updatedAt": now,
    }

    insert_result = workspaces_collection.insert_one(workspace_document)
    workspace_document["_id"] = insert_result.inserted_id
    ensure_workspace_membership(workspace_document["_id"], user_document["_id"], now)
    set_default_workspace(user_document["_id"], insert_result.inserted_id)
    return workspace_document


def ensure_workspace_membership(workspace_id: ObjectId, user_id: ObjectId, now) -> None:
    get_workspace_members_collection().update_one(
        {"workspaceId": workspace_id, "userId": user_id},
        {
            "$set": {
                "workspaceId": workspace_id,
                "userId": user_id,
                "role": "owner",
                "status": "active",
                "updatedAt": now,
            },
            "$setOnInsert": {
                "createdAt": now,
            },
        },
        upsert=True,
    )


def ensure_website_document(
    workspace_document: dict[str, Any],
    snapshot: dict[str, Any],
    website: str,
    website_domain: str,
    now,
) -> dict[str, Any]:
    websites_collection = get_websites_collection()
    analysis_result = snapshot.get("analysisResult", {}) or {}
    analysis = analysis_result.get("analysis", {}) if isinstance(analysis_result, dict) else {}
    contact_signals = analysis_result.get("contactSignals", {}) if isinstance(analysis_result, dict) else {}
    brand_assets = analysis.get("brandAssets") if isinstance(analysis.get("brandAssets"), dict) else {}
    current_website_id = workspace_document.get("currentWebsiteId")

    website_document = None
    if isinstance(current_website_id, ObjectId):
        website_document = websites_collection.find_one({"_id": current_website_id})

    if not website_document and website_domain:
        website_document = websites_collection.find_one(
            {"workspaceId": workspace_document["_id"], "domain": website_domain}
        )

    website_payload = {
        "schemaVersion": SCHEMA_VERSION,
        "workspaceId": workspace_document["_id"],
        "inputUrl": website,
        "canonicalUrl": website,
        "domain": website_domain,
        "brandName": analysis.get("companyName") if isinstance(analysis.get("companyName"), str) else None,
        "logoUrl": analysis.get("logoUrl") if isinstance(analysis.get("logoUrl"), str) else None,
        "brandAssets": repair_value(brand_assets) if isinstance(brand_assets, dict) else {},
        "language": "tr",
        "currencies": [],
        "contactSignals": repair_value(contact_signals) if isinstance(contact_signals, dict) else {},
        "siteSignals": {
            "sector": analysis.get("sector"),
            "offer": analysis.get("offer"),
            "audience": analysis.get("audience"),
            "tone": analysis.get("tone"),
            "pricePosition": analysis.get("pricePosition"),
            "palette": analysis.get("palette") if isinstance(analysis.get("palette"), list) else [],
        },
        "updatedAt": now,
    }

    if website_document:
        websites_collection.update_one(
            {"_id": website_document["_id"]},
            {"$set": website_payload},
        )
        return websites_collection.find_one({"_id": website_document["_id"]}) or website_document

    website_payload["createdAt"] = now
    website_payload["lastCrawlRunId"] = None
    website_payload["lastCrawledAt"] = None
    website_payload["lastAnalysisRunId"] = None
    website_payload["lastAnalysisAt"] = now
    insert_result = websites_collection.insert_one(website_payload)
    website_payload["_id"] = insert_result.inserted_id
    return website_payload


def create_analysis_run(
    workspace_document: dict[str, Any],
    website_document: dict[str, Any],
    user_document: dict[str, Any],
    normalized_email: str | None,
    snapshot: dict[str, Any],
    crawl_run_id: ObjectId | None,
    analysis_fingerprint: str,
    now,
) -> ObjectId:
    analysis_result = snapshot.get("analysisResult", {}) or {}
    analysis = analysis_result.get("analysis", {}) if isinstance(analysis_result, dict) else {}
    source_pages = analysis_result.get("sourcePages", []) if isinstance(analysis_result, dict) else []
    notes = analysis_result.get("notes", []) if isinstance(analysis_result, dict) else []
    memory_files = analysis_result.get("memoryFiles", []) if isinstance(analysis_result, dict) else []
    crawl_pages = analysis_result.get("crawlPages", []) if isinstance(analysis_result, dict) else []
    analysis_meta = analysis_result.get("analysisMeta", {}) if isinstance(analysis_result, dict) else {}
    stored_analysis_result = strip_memory_payload(
        strip_integration_payload(
            strip_crawl_payload(analysis_result) if isinstance(analysis_result, dict) else {}
        )
    )
    if isinstance(stored_analysis_result, dict):
        stored_analysis_result.pop("chatThread", None)
    duplicate_run = get_analysis_runs_collection().find_one(
        {
            "workspaceId": workspace_document["_id"],
            "websiteId": website_document["_id"],
            "analysisFingerprint": analysis_fingerprint,
        },
        sort=[("createdAt", DESCENDING)],
    )
    engine = analysis_meta.get("engine") if isinstance(analysis_meta.get("engine"), str) else "unknown"
    engine_version = (
        analysis_meta.get("engineVersion")
        if isinstance(analysis_meta.get("engineVersion"), str)
        else "unknown"
    )
    prompt_version = (
        analysis_meta.get("promptVersion")
        if isinstance(analysis_meta.get("promptVersion"), str)
        else "unknown"
    )

    analysis_document = {
        "schemaVersion": SCHEMA_VERSION,
        "workspaceId": workspace_document["_id"],
        "websiteId": website_document["_id"],
        "crawlRunId": crawl_run_id,
        "triggeredByUserId": user_document["_id"],
        "triggeredByFirebaseUid": user_document.get("firebaseUid"),
        "emailNormalized": normalized_email,
        "engine": engine,
        "engineVersion": engine_version,
        "promptVersion": prompt_version,
        "selectedGoals": snapshot.get("selectedGoals", [])
        if isinstance(snapshot.get("selectedGoals"), list)
        else [],
        "connectedPlatforms": snapshot.get("connectedPlatforms", [])
        if isinstance(snapshot.get("connectedPlatforms"), list)
        else [],
        "selectedSpecialist": snapshot.get("selectedSpecialist", "aylin"),
        "trialActivated": bool(snapshot.get("trialActivated", False)),
        "analysisFingerprint": analysis_fingerprint,
        "analysisSummary": {
            "companyName": analysis.get("companyName", ""),
            "domain": analysis.get("domain", ""),
            "logoUrl": analysis.get("logoUrl"),
            "brandAssets": repair_value(analysis.get("brandAssets")) if isinstance(analysis.get("brandAssets"), dict) else {},
            "sourcePageCount": len(source_pages) if isinstance(source_pages, list) else len(crawl_pages),
            "crawlPageCount": len(crawl_pages) if isinstance(crawl_pages, list) else 0,
            "memoryFileCount": len(memory_files) if isinstance(memory_files, list) else 0,
            "notesCount": len(notes) if isinstance(notes, list) else 0,
            "analysisFingerprint": analysis_fingerprint,
        },
        "isFingerprintDuplicate": bool(duplicate_run),
        "duplicateOfAnalysisRunId": duplicate_run.get("_id") if duplicate_run else None,
        "memoryDocumentIds": [],
        "analysisResult": stored_analysis_result,
        "createdAt": now,
        "updatedAt": now,
    }

    insert_result = get_analysis_runs_collection().insert_one(analysis_document)
    return insert_result.inserted_id


def get_active_workspace_for_user(user_document: dict[str, Any]) -> dict[str, Any] | None:
    workspaces_collection = get_workspaces_collection()
    default_workspace_id = user_document.get("defaultWorkspaceId")

    if isinstance(default_workspace_id, ObjectId):
        workspace_document = workspaces_collection.find_one({"_id": default_workspace_id})
        if workspace_document:
            return workspace_document

    workspace_document = workspaces_collection.find_one(
        {"ownerUserId": user_document["_id"]},
        sort=[("updatedAt", DESCENDING)],
    )

    if workspace_document and not isinstance(default_workspace_id, ObjectId):
        set_default_workspace(user_document["_id"], workspace_document["_id"])

    return workspace_document


def get_current_website_for_workspace(workspace_document: dict[str, Any]) -> dict[str, Any] | None:
    current_website_id = workspace_document.get("currentWebsiteId")
    if isinstance(current_website_id, ObjectId):
        return get_websites_collection().find_one({"_id": current_website_id})

    return get_websites_collection().find_one(
        {"workspaceId": workspace_document["_id"]},
        sort=[("updatedAt", DESCENDING)],
    )


def get_latest_analysis_run_for_workspace(workspace_document: dict[str, Any]) -> dict[str, Any] | None:
    latest_analysis_run_id = workspace_document.get("latestAnalysisRunId")
    if isinstance(latest_analysis_run_id, ObjectId):
        analysis_document = get_analysis_runs_collection().find_one({"_id": latest_analysis_run_id})
        if analysis_document:
            return analysis_document

    return get_analysis_runs_collection().find_one(
        {"workspaceId": workspace_document["_id"]},
        sort=[("createdAt", DESCENDING)],
    )


def build_workspace_snapshot_response(
    workspace_document: dict[str, Any],
    website_document: dict[str, Any] | None,
    analysis_run_document: dict[str, Any],
) -> dict[str, Any]:
    current_state = workspace_document.get("currentState", {}) if isinstance(workspace_document, dict) else {}
    trial = workspace_document.get("trial", {}) if isinstance(workspace_document, dict) else {}
    crawl_run_document = None
    crawl_run_id = analysis_run_document.get("crawlRunId")
    if isinstance(crawl_run_id, ObjectId):
        crawl_run_document = get_latest_crawl_run_for_workspace(
            {
                "_id": workspace_document["_id"],
                "latestCrawlRunId": crawl_run_id,
            }
        )
    if not crawl_run_document:
        crawl_run_document = get_latest_crawl_run_for_workspace(workspace_document)

    crawled_pages = (
        get_crawled_pages_for_run(crawl_run_document["_id"])
        if isinstance(crawl_run_document, dict) and isinstance(crawl_run_document.get("_id"), ObjectId)
        else []
    )
    analysis_result = enrich_analysis_result_with_crawl_data(
        analysis_run_document.get("analysisResult", {}),
        crawl_run_document,
        crawled_pages,
    )
    integration_connections = get_integration_connections_for_workspace(workspace_document)
    integration_sync_runs = get_recent_integration_sync_runs_for_workspace(workspace_document)
    analysis_result = enrich_analysis_result_with_integrations(
        analysis_result,
        integration_connections,
        integration_sync_runs,
    )
    memory_documents = get_memory_documents_for_analysis_run(analysis_run_document)
    analysis_result = enrich_analysis_result_with_memory_files(
        analysis_result,
        memory_documents,
    )
    thread_document = get_latest_thread_for_workspace(workspace_document)
    message_documents = (
        get_messages_for_thread(thread_document["_id"])
        if isinstance(thread_document, dict) and isinstance(thread_document.get("_id"), ObjectId)
        else []
    )
    analysis_result = enrich_analysis_result_with_chat_thread(
        analysis_result,
        thread_document,
        message_documents,
    )

    website_value = ""
    if isinstance(website_document, dict):
        website_value = str(
            website_document.get("inputUrl")
            or website_document.get("canonicalUrl")
            or ""
        ).strip()

    if not website_value and isinstance(current_state, dict):
        website_value = str(current_state.get("website") or "").strip()

    return {
        "website": website_value,
        "selectedGoals": current_state.get("selectedGoals", []) if isinstance(current_state, dict) else [],
        "connectedPlatforms": current_state.get("connectedPlatforms", []) if isinstance(current_state, dict) else [],
        "analysisResult": analysis_result,
        "trialActivated": bool(trial.get("activated", False)) if isinstance(trial, dict) else False,
        "selectedSpecialist": workspace_document.get("selectedSpecialist", "aylin"),
    }


def migrate_legacy_snapshot_if_present(user_id: str, email: str | None) -> dict[str, Any] | None:
    legacy_document = None
    normalized_email = normalize_email(email)
    legacy_collection = get_legacy_workspace_collection()

    if user_id:
        legacy_document = legacy_collection.find_one({"firebaseUserId": user_id})

    if not legacy_document and normalized_email:
        legacy_document = legacy_collection.find_one({"emailNormalized": normalized_email})

    if not legacy_document:
        return None

    legacy_snapshot = strip_legacy_metadata(repair_value(legacy_document))
    save_workspace_snapshot(user_id, email, legacy_snapshot)
    legacy_collection.delete_one({"_id": legacy_document["_id"]})
    return get_workspace_snapshot(user_id, email)


def build_workspace_name(snapshot: dict[str, Any], user_document: dict[str, Any]) -> str:
    analysis_result = snapshot.get("analysisResult", {}) if isinstance(snapshot, dict) else {}
    analysis = analysis_result.get("analysis", {}) if isinstance(analysis_result, dict) else {}
    company_name = analysis.get("companyName")
    if isinstance(company_name, str) and company_name.strip():
        return company_name.strip()

    email = user_document.get("email")
    if isinstance(email, str) and email.strip():
        return email.split("@")[0].strip()

    display_name = user_document.get("displayName")
    if isinstance(display_name, str) and display_name.strip():
        return display_name.strip()

    return "Acrtech Workspace"


def build_workspace_slug(name: str, firebase_uid: str) -> str:
    normalized_name = re.sub(r"[^a-z0-9]+", "-", repair_text(name).lower()).strip("-")
    base = normalized_name or "workspace"
    suffix = firebase_uid[:8] if firebase_uid else hashlib.sha1(base.encode("utf-8")).hexdigest()[:8]
    return f"{base}-{suffix}"


def infer_website_domain(website: str, analysis: dict[str, Any]) -> str:
    domain = analysis.get("domain")
    if isinstance(domain, str) and domain.strip():
        return domain.strip().lower()

    candidate = website.replace("https://", "").replace("http://", "").split("/")[0].strip().lower()
    return candidate.replace("www.", "")


def build_analysis_fingerprint(
    user_id: str,
    website: str,
    analysis_result: dict[str, Any],
) -> str:
    normalized_analysis_result = repair_value(analysis_result) if isinstance(analysis_result, dict) else {}
    if isinstance(normalized_analysis_result, dict):
        normalized_analysis_result.pop("chatThread", None)
        normalized_analysis_result.pop("integrationConnections", None)
        normalized_analysis_result.pop("integrationSyncRuns", None)

    payload = {
        "userId": user_id,
        "website": website,
        "analysisResult": normalized_analysis_result,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def strip_legacy_metadata(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "website": snapshot.get("website", ""),
        "selectedGoals": snapshot.get("selectedGoals", []),
        "connectedPlatforms": snapshot.get("connectedPlatforms", []),
        "analysisResult": snapshot.get("analysisResult", {}),
        "trialActivated": bool(snapshot.get("trialActivated", False)),
        "selectedSpecialist": snapshot.get("selectedSpecialist", "aylin"),
    }


def repair_value(value: Any) -> Any:
    if isinstance(value, str):
        return repair_text(value)

    if isinstance(value, list):
        return [repair_value(item) for item in value]

    if isinstance(value, dict):
        return {key: repair_value(item) for key, item in value.items() if key != "_id"}

    return value


def repair_text(value: str) -> str:
    if not any(marker in value for marker in ("ÃƒÆ’", "Ãƒâ€¦", "Ãƒâ€", "ÃƒÂ¢")):
        return value

    try:
        return value.encode("latin1").decode("utf-8")
    except Exception:
        return value
