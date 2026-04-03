from __future__ import annotations

from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from .database import get_database


SCHEMA_VERSION = 5
CHAT_THREAD_COLLECTION_NAME = "chat_threads"
CHAT_MESSAGE_COLLECTION_NAME = "chat_messages"
ANALYSIS_PROCESS_STEPS = [
    "İçeriğini çekiyorum",
    "Önemli sayfaları ve teklif yapını tarıyorum",
    "Pazar ve fırsat sinyallerini yorumluyorum",
    "Hafıza dosyalarını kaydediyorum",
]


def get_chat_threads_collection():
    return get_database()[CHAT_THREAD_COLLECTION_NAME]


def get_chat_messages_collection():
    return get_database()[CHAT_MESSAGE_COLLECTION_NAME]


def ensure_chat_indexes() -> None:
    threads = get_chat_threads_collection()
    messages = get_chat_messages_collection()

    threads.create_index(
        [("workspaceId", ASCENDING), ("updatedAt", DESCENDING)],
        name="chat_threads_workspace_updated_at",
    )
    threads.create_index(
        [("createdByUserId", ASCENDING), ("updatedAt", DESCENDING)],
        name="chat_threads_created_by_updated_at",
    )
    threads.create_index(
        [("status", ASCENDING), ("updatedAt", DESCENDING)],
        name="chat_threads_status_updated_at",
    )

    messages.create_index(
        [("threadId", ASCENDING), ("sequence", ASCENDING)],
        unique=True,
        name="chat_messages_thread_sequence_unique",
    )
    messages.create_index(
        [("workspaceId", ASCENDING), ("createdAt", DESCENDING)],
        name="chat_messages_workspace_created_at",
    )
    messages.create_index(
        [("relatedAnalysisRunId", ASCENDING), ("threadId", ASCENDING)],
        sparse=True,
        name="chat_messages_analysis_thread",
    )


def create_or_update_analysis_thread(
    workspace_document: dict[str, Any],
    user_document: dict[str, Any],
    analysis_run_document: dict[str, Any],
    memory_documents: list[dict[str, Any]],
    analysis_result: dict[str, Any] | None,
    specialist_id: str,
    now,
) -> ObjectId:
    thread_document = ensure_workspace_thread(
        workspace_document=workspace_document,
        user_document=user_document,
        analysis_result=analysis_result,
        now=now,
    )
    related_analysis_run_id = analysis_run_document.get("_id")
    if not isinstance(related_analysis_run_id, ObjectId):
        return thread_document["_id"]

    existing_summary_message = get_chat_messages_collection().find_one(
        {
            "threadId": thread_document["_id"],
            "relatedAnalysisRunId": related_analysis_run_id,
            "messageType": "analysis_summary",
        }
    )
    if existing_summary_message:
        return thread_document["_id"]

    timeline_messages = build_chat_timeline_messages(
        analysis_result=analysis_result,
        memory_documents=memory_documents,
        related_analysis_run_id=related_analysis_run_id,
        specialist_id=specialist_id,
    )

    last_message = get_chat_messages_collection().find_one(
        {"threadId": thread_document["_id"]},
        sort=[("sequence", DESCENDING)],
    )
    next_sequence = int(last_message.get("sequence", 0)) + 1 if isinstance(last_message, dict) else 1

    documents = []
    for offset, message in enumerate(timeline_messages):
        documents.append(
            {
                "schemaVersion": SCHEMA_VERSION,
                "threadId": thread_document["_id"],
                "workspaceId": workspace_document["_id"],
                "senderType": message["senderType"],
                "senderId": message["senderId"],
                "messageType": message["messageType"],
                "content": message["content"],
                "attachments": message.get("attachments", []),
                "metadata": message.get("metadata", {}),
                "relatedAnalysisRunId": related_analysis_run_id,
                "relatedMemoryDocumentIds": [
                    document["_id"] for document in memory_documents if isinstance(document.get("_id"), ObjectId)
                ],
                "sequence": next_sequence + offset,
                "createdAt": now,
            }
        )

    if documents:
        get_chat_messages_collection().insert_many(documents, ordered=True)
        get_chat_threads_collection().update_one(
            {"_id": thread_document["_id"]},
            {
                "$set": {
                    "latestAnalysisRunId": related_analysis_run_id,
                    "lastMessageAt": now,
                    "updatedAt": now,
                }
            },
        )

    return thread_document["_id"]


def ensure_workspace_thread(
    workspace_document: dict[str, Any],
    user_document: dict[str, Any],
    analysis_result: dict[str, Any] | None,
    now,
) -> dict[str, Any]:
    threads = get_chat_threads_collection()
    latest_thread_id = workspace_document.get("latestThreadId")
    if isinstance(latest_thread_id, ObjectId):
        thread_document = threads.find_one({"_id": latest_thread_id})
        if thread_document:
            return thread_document

    thread_document = threads.find_one(
        {"workspaceId": workspace_document["_id"], "status": "active"},
        sort=[("updatedAt", DESCENDING)],
    )
    if thread_document:
        return thread_document

    analysis = analysis_result.get("analysis", {}) if isinstance(analysis_result, dict) else {}
    company_name = analysis.get("companyName") if isinstance(analysis.get("companyName"), str) else ""
    title = f"{company_name} için ilk analiz" if company_name else "İlk analiz"
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "workspaceId": workspace_document["_id"],
        "title": title,
        "status": "active",
        "createdByUserId": user_document["_id"],
        "createdByFirebaseUid": user_document.get("firebaseUid"),
        "latestAnalysisRunId": None,
        "lastMessageAt": now,
        "createdAt": now,
        "updatedAt": now,
    }
    insert_result = threads.insert_one(payload)
    payload["_id"] = insert_result.inserted_id
    return payload


def get_latest_thread_for_workspace(workspace_document: dict[str, Any]) -> dict[str, Any] | None:
    latest_thread_id = workspace_document.get("latestThreadId")
    if isinstance(latest_thread_id, ObjectId):
        thread_document = get_chat_threads_collection().find_one({"_id": latest_thread_id})
        if thread_document:
            return thread_document

    return get_chat_threads_collection().find_one(
        {"workspaceId": workspace_document["_id"]},
        sort=[("updatedAt", DESCENDING)],
    )


def get_messages_for_thread(thread_id: ObjectId, limit: int | None = None) -> list[dict[str, Any]]:
    cursor = get_chat_messages_collection().find(
        {"threadId": thread_id},
        sort=[("sequence", ASCENDING)],
    )
    if isinstance(limit, int) and limit > 0:
        cursor = cursor.limit(limit)
    return list(cursor)


def enrich_analysis_result_with_chat_thread(
    analysis_result: dict[str, Any] | None,
    thread_document: dict[str, Any] | None,
    message_documents: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    result = repair_value(analysis_result or {})
    if not thread_document:
        return result

    result["chatThread"] = serialize_chat_thread(thread_document, message_documents or [])
    return result


def build_ephemeral_chat_thread(
    analysis_result: dict[str, Any] | None,
    specialist_id: str = "aylin",
) -> dict[str, Any]:
    cleaned_result = repair_value(analysis_result or {})
    analysis = cleaned_result.get("analysis", {}) if isinstance(cleaned_result, dict) else {}
    company_name = analysis.get("companyName") if isinstance(analysis.get("companyName"), str) else ""
    memory_files = cleaned_result.get("memoryFiles", []) if isinstance(cleaned_result, dict) else []
    memory_documents = [
        {
            "id": item.get("id", ""),
            "filename": item.get("filename", ""),
            "title": item.get("title", ""),
            "blurb": item.get("blurb", ""),
            "markdown": item.get("content", ""),
            "version": item.get("version", 1) or 1,
            "isCurrent": item.get("isCurrent", True),
        }
        for item in memory_files
        if isinstance(item, dict)
    ]
    messages = build_chat_timeline_messages(
        analysis_result=cleaned_result,
        memory_documents=memory_documents,
        related_analysis_run_id=None,
        specialist_id=specialist_id,
    )
    return {
        "id": "ephemeral-thread",
        "title": f"{company_name} için ilk analiz" if company_name else "İlk analiz",
        "status": "active",
        "messages": [
            serialize_ephemeral_message(index + 1, message)
            for index, message in enumerate(messages)
        ],
    }


def build_chat_timeline_messages(
    analysis_result: dict[str, Any] | None,
    memory_documents: list[dict[str, Any]],
    related_analysis_run_id: ObjectId | None,
    specialist_id: str,
) -> list[dict[str, Any]]:
    cleaned_result = repair_value(analysis_result or {})
    analysis = cleaned_result.get("analysis", {}) if isinstance(cleaned_result, dict) else {}
    strategic_summary = cleaned_result.get("strategicSummary", {}) if isinstance(cleaned_result, dict) else {}
    quality_review = cleaned_result.get("qualityReview", {}) if isinstance(cleaned_result, dict) else {}

    attachments = [serialize_memory_attachment(document) for document in memory_documents]
    first_drop_attachments = attachments[:2]
    second_drop_attachments = attachments[2:4] if len(attachments) > 2 else attachments
    inline_files = ", ".join(
        attachment.get("filename", "")
        for attachment in attachments
        if isinstance(attachment.get("filename"), str) and attachment.get("filename")
    )

    summary_message = (
        f"İlk bakış güçlü. {analysis.get('companyName', 'Bu marka')}, "
        f"{get_non_empty_string(strategic_summary.get('positioning')) or analysis.get('offer', 'belirgin bir değer önerisi')} "
        f"etrafında konumlanıyor gibi görünüyor. "
        f"En olası hedef kitle {get_non_empty_string(strategic_summary.get('bestFitAudience')) or analysis.get('audience', 'hedef kitle sinyalleri')} "
        f"ve ayırıcı çizgi {get_non_empty_string(strategic_summary.get('differentiation')) or 'teklif yapısında saklı'}."
    )
    deep_dive_message = (
        f"Şimdi biraz daha derine iniyorum. En güçlü kaldıraç şu anda "
        f"{get_non_empty_string(strategic_summary.get('primaryGrowthLever')) or analysis.get('opportunity', 'büyüme fırsatı')} "
        f"çizgisinde görünüyor. İçerik açısından ise "
        f"{get_non_empty_string(strategic_summary.get('contentAngle')) or 'daha güçlü bir konu kümelenmesi'} öne çıkıyor."
    )
    final_message = "Dosyaları kaydettim."
    if inline_files:
        final_message = f"{final_message} {inline_files} hazır."
    if isinstance(analysis.get("opportunity"), str) and analysis.get("opportunity"):
        final_message = f"{final_message} En dikkat çekici büyüme fırsatı şu: {analysis['opportunity']}"
    quality_score = positive_int(quality_review.get("score"), 0)
    if quality_score:
        final_message = f"{final_message} Analiz kapsam puanı şu anda {quality_score}/100."

    return [
        {
            "senderType": "assistant",
            "senderId": specialist_id,
            "messageType": "assistant_text",
            "content": (
                "Web sitenizi inceleyelim ve pazarlama temellerinizi oluşturmaya başlayalım. "
                "Teklif yapınızı, ürünlerinizi, güven sinyallerinizi ve kategori ipuçlarını tek bir çalışma akışında bir araya getiriyorum."
            ),
            "attachments": [],
            "metadata": {},
        },
        {
            "senderType": "system",
            "senderId": "analysis-pipeline",
            "messageType": "process",
            "content": "Analiz hattı tamamlandı.",
            "attachments": [],
            "metadata": {
                "tasks": ANALYSIS_PROCESS_STEPS,
                "relatedAnalysisRunId": str(related_analysis_run_id) if related_analysis_run_id else None,
            },
        },
        {
            "senderType": "assistant",
            "senderId": specialist_id,
            "messageType": "assistant_text",
            "content": summary_message,
            "attachments": [],
            "metadata": {},
        },
        {
            "senderType": "assistant",
            "senderId": specialist_id,
            "messageType": "memory_files",
            "content": "Önce işletme profili ve marka kılavuzunu oluşturmaya başlıyorum.",
            "attachments": first_drop_attachments,
            "metadata": {
                "memoryCount": len(first_drop_attachments),
            },
        },
        {
            "senderType": "assistant",
            "senderId": specialist_id,
            "messageType": "assistant_text",
            "content": deep_dive_message,
            "attachments": [],
            "metadata": {},
        },
        {
            "senderType": "assistant",
            "senderId": specialist_id,
            "messageType": "memory_files",
            "content": "Şimdi pazar araştırması ve strateji dosyalarını netleştiriyorum.",
            "attachments": second_drop_attachments,
            "metadata": {
                "memoryCount": len(second_drop_attachments),
            },
        },
        {
            "senderType": "assistant",
            "senderId": specialist_id,
            "messageType": "analysis_summary",
            "content": final_message,
            "attachments": attachments,
            "metadata": {},
        },
    ]


def serialize_chat_thread(thread_document: dict[str, Any], messages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": str(thread_document.get("_id", "")),
        "title": get_non_empty_string(thread_document.get("title")) or "İlk analiz",
        "status": get_non_empty_string(thread_document.get("status")) or "active",
        "messages": [serialize_chat_message(document) for document in messages],
    }


def serialize_chat_message(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(document.get("_id", "")),
        "senderType": get_non_empty_string(document.get("senderType")) or "assistant",
        "senderId": get_non_empty_string(document.get("senderId")) or "aylin",
        "messageType": get_non_empty_string(document.get("messageType")) or "assistant_text",
        "content": get_non_empty_string(document.get("content")),
        "attachments": normalize_attachments(document.get("attachments")),
        "metadata": normalize_metadata(document.get("metadata")),
        "relatedAnalysisRunId": str(document.get("relatedAnalysisRunId", "")) if document.get("relatedAnalysisRunId") else None,
        "createdAt": document.get("createdAt").isoformat() if document.get("createdAt") else None,
    }


def serialize_ephemeral_message(sequence: int, message: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"ephemeral-{sequence}",
        "senderType": message["senderType"],
        "senderId": message["senderId"],
        "messageType": message["messageType"],
        "content": message["content"],
        "attachments": normalize_attachments(message.get("attachments")),
        "metadata": normalize_metadata(message.get("metadata")),
        "relatedAnalysisRunId": None,
        "createdAt": None,
    }


def serialize_memory_attachment(document: dict[str, Any]) -> dict[str, Any]:
    document_id = document.get("_id")
    return {
        "type": "memory_document",
        "id": str(document_id) if isinstance(document_id, ObjectId) else get_non_empty_string(document.get("id")),
        "fileId": get_non_empty_string(document.get("id")),
        "filename": get_non_empty_string(document.get("filename")),
        "title": get_non_empty_string(document.get("title")),
        "blurb": get_non_empty_string(document.get("blurb")),
        "version": positive_int(document.get("version"), 1),
        "isCurrent": bool(document.get("isCurrent", True)),
    }


def normalize_attachments(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    attachments: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        attachments.append(
            {
                "type": get_non_empty_string(item.get("type")) or "memory_document",
                "id": get_non_empty_string(item.get("id")),
                "fileId": get_non_empty_string(item.get("fileId")),
                "filename": get_non_empty_string(item.get("filename")),
                "title": get_non_empty_string(item.get("title")),
                "blurb": get_non_empty_string(item.get("blurb")),
                "version": positive_int(item.get("version"), 1),
                "isCurrent": bool(item.get("isCurrent", True)),
            }
        )
    return attachments


def normalize_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, str):
            clean_item = item.strip()
            if clean_item:
                result[key] = clean_item
        elif isinstance(item, list):
            result[key] = [entry for entry in item if isinstance(entry, str) and entry.strip()]
        elif item is None:
            result[key] = None
    return result


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
    if not any(marker in value for marker in ("ÃƒÆ’Ã†â€™", "Ãƒâ€¦", "Ãƒâ€", "ÃƒÂ¢")):
        return value
    try:
        return value.encode("latin1").decode("utf-8")
    except Exception:
        return value
