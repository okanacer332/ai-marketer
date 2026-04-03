from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from .database import get_database


SCHEMA_VERSION = 4
MEMORY_DOCUMENT_COLLECTION_NAME = "memory_documents"
DEFAULT_MEMORY_ORDER = [
    "business-profile",
    "brand-guidelines",
    "market-research",
    "strategy",
]


def get_memory_documents_collection():
    return get_database()[MEMORY_DOCUMENT_COLLECTION_NAME]


def ensure_memory_indexes() -> None:
    collection = get_memory_documents_collection()
    collection.create_index(
        [("workspaceId", ASCENDING), ("websiteId", ASCENDING), ("kind", ASCENDING), ("isCurrent", ASCENDING)],
        name="memory_documents_workspace_kind_current",
    )
    collection.create_index(
        [("workspaceId", ASCENDING), ("websiteId", ASCENDING), ("kind", ASCENDING)],
        unique=True,
        partialFilterExpression={"isCurrent": True},
        name="memory_documents_workspace_kind_current_unique",
    )
    collection.create_index(
        [("analysisRunId", ASCENDING), ("displayOrder", ASCENDING)],
        name="memory_documents_analysis_run_display_order",
    )
    collection.create_index(
        [("workspaceId", ASCENDING), ("updatedAt", DESCENDING)],
        name="memory_documents_workspace_updated_at",
    )
    collection.create_index(
        [("contentHash", ASCENDING)],
        name="memory_documents_content_hash",
    )


def create_or_reuse_memory_documents(
    workspace_document: dict[str, Any],
    website_document: dict[str, Any],
    analysis_run_id: ObjectId,
    analysis_result: dict[str, Any] | None,
    now,
) -> list[ObjectId]:
    memory_files = normalize_memory_files(
        analysis_result.get("memoryFiles", []) if isinstance(analysis_result, dict) else []
    )
    if not memory_files:
        return []

    collection = get_memory_documents_collection()
    document_ids: list[ObjectId] = []

    for display_order, memory_file in enumerate(memory_files):
        kind = infer_memory_kind(memory_file, display_order)
        content_hash = build_memory_content_hash(memory_file, kind)
        current_document = collection.find_one(
            {
                "workspaceId": workspace_document["_id"],
                "websiteId": website_document["_id"],
                "kind": kind,
                "isCurrent": True,
            }
        )

        if current_document and current_document.get("contentHash") == content_hash:
            collection.update_one(
                {"_id": current_document["_id"]},
                {
                    "$set": {
                        "updatedAt": now,
                        "lastReferencedAnalysisRunId": analysis_run_id,
                    }
                },
            )
            document_ids.append(current_document["_id"])
            continue

        latest_document = collection.find_one(
            {
                "workspaceId": workspace_document["_id"],
                "websiteId": website_document["_id"],
                "kind": kind,
            },
            sort=[("version", DESCENDING), ("updatedAt", DESCENDING)],
        )
        next_version = int(latest_document.get("version", 0)) + 1 if latest_document else 1

        collection.update_many(
            {
                "workspaceId": workspace_document["_id"],
                "websiteId": website_document["_id"],
                "kind": kind,
                "isCurrent": True,
            },
            {"$set": {"isCurrent": False, "updatedAt": now}},
        )

        document_payload = {
            "schemaVersion": SCHEMA_VERSION,
            "workspaceId": workspace_document["_id"],
            "websiteId": website_document["_id"],
            "analysisRunId": analysis_run_id,
            "kind": kind,
            "displayOrder": display_order,
            "id": memory_file["id"],
            "filename": memory_file["filename"],
            "title": memory_file["title"],
            "blurb": memory_file["blurb"],
            "markdown": memory_file["content"],
            "contentHash": content_hash,
            "version": next_version,
            "isCurrent": True,
            "createdAt": now,
            "updatedAt": now,
            "lastReferencedAnalysisRunId": analysis_run_id,
        }
        insert_result = collection.insert_one(document_payload)
        document_ids.append(insert_result.inserted_id)

    return document_ids


def get_memory_documents_for_analysis_run(analysis_run_document: dict[str, Any]) -> list[dict[str, Any]]:
    memory_document_ids = analysis_run_document.get("memoryDocumentIds")
    if isinstance(memory_document_ids, list) and memory_document_ids:
        valid_ids = [document_id for document_id in memory_document_ids if isinstance(document_id, ObjectId)]
        if valid_ids:
            documents = list(
                get_memory_documents_collection().find({"_id": {"$in": valid_ids}})
            )
            documents_by_id = {document["_id"]: document for document in documents}
            ordered_documents = [documents_by_id[document_id] for document_id in valid_ids if document_id in documents_by_id]
            if ordered_documents:
                return ordered_documents

    analysis_run_id = analysis_run_document.get("_id")
    if isinstance(analysis_run_id, ObjectId):
        documents = list(
            get_memory_documents_collection().find(
                {"analysisRunId": analysis_run_id},
                sort=[("displayOrder", ASCENDING), ("updatedAt", DESCENDING)],
            )
        )
        if documents:
            return documents

    workspace_id = analysis_run_document.get("workspaceId")
    website_id = analysis_run_document.get("websiteId")
    if isinstance(workspace_id, ObjectId) and isinstance(website_id, ObjectId):
        return get_current_memory_documents(workspace_id, website_id)

    return []


def get_current_memory_documents(workspace_id: ObjectId, website_id: ObjectId) -> list[dict[str, Any]]:
    documents = list(
        get_memory_documents_collection().find(
            {"workspaceId": workspace_id, "websiteId": website_id, "isCurrent": True}
        )
    )
    return sort_memory_documents(documents)


def enrich_analysis_result_with_memory_files(
    analysis_result: dict[str, Any] | None,
    memory_documents: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    result = repair_value(analysis_result or {})

    if not memory_documents:
        return result

    result["memoryFiles"] = [serialize_memory_document(document) for document in sort_memory_documents(memory_documents)]
    return result


def strip_memory_payload(analysis_result: dict[str, Any] | None) -> dict[str, Any]:
    cleaned_result = repair_value(analysis_result or {})
    if isinstance(cleaned_result, dict):
        cleaned_result.pop("memoryFiles", None)
    return cleaned_result


def serialize_memory_document(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": get_non_empty_string(document.get("id")) or infer_memory_id_from_kind(get_non_empty_string(document.get("kind"))),
        "filename": get_non_empty_string(document.get("filename")),
        "title": get_non_empty_string(document.get("title")),
        "blurb": get_non_empty_string(document.get("blurb")),
        "content": get_non_empty_string(document.get("markdown")),
        "version": positive_int(document.get("version"), 1),
        "isCurrent": bool(document.get("isCurrent", False)),
    }


def normalize_memory_files(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    normalized: list[dict[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        filename = get_non_empty_string(item.get("filename")) or f"memory-{index + 1}.md"
        normalized.append(
            {
                "id": get_non_empty_string(item.get("id")) or infer_memory_id_from_filename(filename, index),
                "filename": filename,
                "title": get_non_empty_string(item.get("title")) or f"Dokuman {index + 1}",
                "blurb": get_non_empty_string(item.get("blurb")),
                "content": get_non_empty_string(item.get("content")),
            }
        )
    return [item for item in normalized if item["content"]]


def infer_memory_kind(memory_file: dict[str, str], index: int) -> str:
    for candidate in (
        memory_file.get("id", ""),
        infer_memory_id_from_filename(memory_file.get("filename", ""), index),
        slugify(memory_file.get("title", "")),
    ):
        if candidate:
            return candidate
    return DEFAULT_MEMORY_ORDER[index] if index < len(DEFAULT_MEMORY_ORDER) else f"memory-{index + 1}"


def infer_memory_id_from_filename(filename: str, index: int) -> str:
    name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    stem = name[:-3] if name.lower().endswith(".md") else name
    candidate = slugify(stem)
    if candidate:
        return candidate
    return DEFAULT_MEMORY_ORDER[index] if index < len(DEFAULT_MEMORY_ORDER) else f"memory-{index + 1}"


def infer_memory_id_from_kind(kind: str) -> str:
    return slugify(kind) or "memory"


def build_memory_content_hash(memory_file: dict[str, str], kind: str) -> str:
    payload = "|".join(
        [
            kind,
            memory_file.get("filename", ""),
            memory_file.get("title", ""),
            memory_file.get("blurb", ""),
            memory_file.get("content", ""),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sort_memory_documents(documents: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    order_map = {kind: index for index, kind in enumerate(DEFAULT_MEMORY_ORDER)}
    return sorted(
        documents,
        key=lambda document: (
            int(document.get("displayOrder", 9999)),
            order_map.get(get_non_empty_string(document.get("kind")), 9999),
            get_non_empty_string(document.get("filename")),
        ),
    )


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


def positive_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value if value >= 0 else default
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
    return default


def get_non_empty_string(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def repair_value(value: Any) -> Any:
    if isinstance(value, str):
        return repair_text(value)
    if isinstance(value, list):
        return [repair_value(item) for item in value]
    if isinstance(value, dict):
        return {key: repair_value(item) for key, item in value.items() if key != "_id"}
    return value


def repair_text(value: str) -> str:
    if not any(marker in value for marker in ("ÃƒÆ’Ã†â€™", "ÃƒÆ’Ã¢â‚¬Â¦", "ÃƒÆ’Ã¢â‚¬Â", "ÃƒÆ’Ã‚Â¢")):
        return value
    try:
        return value.encode("latin1").decode("utf-8")
    except Exception:
        return value
