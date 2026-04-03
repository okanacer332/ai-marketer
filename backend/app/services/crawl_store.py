from __future__ import annotations

from typing import Any, Iterable
from urllib.parse import urlparse, urlunparse

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from .database import get_database


SCHEMA_VERSION = 3
CRAWL_RUN_COLLECTION_NAME = "crawl_runs"
CRAWLED_PAGE_COLLECTION_NAME = "crawled_pages"


def get_crawl_runs_collection():
    return get_database()[CRAWL_RUN_COLLECTION_NAME]


def get_crawled_pages_collection():
    return get_database()[CRAWLED_PAGE_COLLECTION_NAME]


def ensure_crawl_indexes() -> None:
    crawl_runs_collection = get_crawl_runs_collection()
    crawled_pages_collection = get_crawled_pages_collection()

    crawl_runs_collection.create_index(
        [("workspaceId", ASCENDING), ("createdAt", DESCENDING)],
        name="crawl_runs_workspace_created_at",
    )
    crawl_runs_collection.create_index(
        [("websiteId", ASCENDING), ("createdAt", DESCENDING)],
        name="crawl_runs_website_created_at",
    )
    crawl_runs_collection.create_index(
        [("triggeredByUserId", ASCENDING), ("createdAt", DESCENDING)],
        name="crawl_runs_user_created_at",
    )
    crawl_runs_collection.create_index(
        [("status", ASCENDING), ("createdAt", DESCENDING)],
        name="crawl_runs_status_created_at",
    )

    crawled_pages_collection.create_index(
        [("crawlRunId", ASCENDING), ("pageIndex", ASCENDING)],
        name="crawled_pages_run_page_index",
    )
    crawled_pages_collection.create_index(
        [("websiteId", ASCENDING), ("normalizedUrl", ASCENDING)],
        name="crawled_pages_website_normalized_url",
    )
    crawled_pages_collection.create_index(
        [("websiteId", ASCENDING), ("createdAt", DESCENDING)],
        name="crawled_pages_website_created_at",
    )
    crawled_pages_collection.create_index(
        [("pageType", ASCENDING), ("fetchMode", ASCENDING)],
        name="crawled_pages_page_type_fetch_mode",
    )


def create_crawl_records(
    workspace_document: dict[str, Any],
    website_document: dict[str, Any],
    user_document: dict[str, Any],
    analysis_result: dict[str, Any] | None,
    now,
) -> ObjectId | None:
    cleaned_result = repair_value(analysis_result or {})
    crawl_meta = cleaned_result.get("crawlMeta", {}) if isinstance(cleaned_result, dict) else {}
    source_pages = cleaned_result.get("sourcePages", []) if isinstance(cleaned_result, dict) else []
    notes = cleaned_result.get("notes", []) if isinstance(cleaned_result, dict) else []
    crawl_pages = build_crawl_pages_payload(
        cleaned_result.get("crawlPages", []) if isinstance(cleaned_result, dict) else [],
        source_pages,
    )

    normalized_notes = normalize_string_list(crawl_meta.get("notes")) or normalize_string_list(notes)
    pages_succeeded = positive_int(crawl_meta.get("pagesSucceeded"), len(crawl_pages))
    pages_visited = positive_int(crawl_meta.get("pagesVisited"), max(len(crawl_pages), pages_succeeded))
    pages_failed = positive_int(crawl_meta.get("pagesFailed"), max(0, pages_visited - pages_succeeded))
    page_limit = positive_int(crawl_meta.get("pageLimit"), max(len(crawl_pages), pages_succeeded, 1))
    depth_limit = positive_int(crawl_meta.get("depthLimit"), 2)
    render_modes = normalize_string_list(crawl_meta.get("renderModes")) or unique_ordered(
        page.get("fetchMode", "") for page in crawl_pages
    )
    fetch_strategy = get_non_empty_string(crawl_meta.get("fetchStrategy")) or infer_fetch_strategy(render_modes)
    sitemap_urls = normalize_string_list(crawl_meta.get("sitemapUrls"))
    status = get_non_empty_string(crawl_meta.get("status")) or (
        "partial" if pages_failed or pages_visited > pages_succeeded else "completed"
    )

    if not crawl_pages and not normalized_notes:
        return None

    crawl_run_document = {
        "schemaVersion": SCHEMA_VERSION,
        "workspaceId": workspace_document["_id"],
        "websiteId": website_document["_id"],
        "triggeredByUserId": user_document["_id"],
        "triggeredByFirebaseUid": user_document.get("firebaseUid"),
        "status": status,
        "fetchStrategy": fetch_strategy,
        "pageLimit": page_limit,
        "depthLimit": depth_limit,
        "pagesVisited": pages_visited,
        "pagesSucceeded": pages_succeeded,
        "pagesFailed": pages_failed,
        "notes": normalized_notes[:24],
        "renderModes": render_modes[:8],
        "sitemapUrls": sitemap_urls[:20],
        "startedAt": now,
        "finishedAt": now,
        "createdAt": now,
    }

    crawl_run_result = get_crawl_runs_collection().insert_one(crawl_run_document)
    crawl_run_id = crawl_run_result.inserted_id

    page_documents = [
        build_crawled_page_document(
            crawl_run_id=crawl_run_id,
            website_id=website_document["_id"],
            page_index=index,
            page_payload=page_payload,
            now=now,
        )
        for index, page_payload in enumerate(crawl_pages)
    ]

    if page_documents:
        get_crawled_pages_collection().insert_many(page_documents, ordered=True)

    return crawl_run_id


def get_latest_crawl_run_for_workspace(workspace_document: dict[str, Any]) -> dict[str, Any] | None:
    latest_crawl_run_id = workspace_document.get("latestCrawlRunId")
    if isinstance(latest_crawl_run_id, ObjectId):
        crawl_run_document = get_crawl_runs_collection().find_one({"_id": latest_crawl_run_id})
        if crawl_run_document:
            return crawl_run_document

    return get_crawl_runs_collection().find_one(
        {"workspaceId": workspace_document["_id"]},
        sort=[("createdAt", DESCENDING)],
    )


def get_crawled_pages_for_run(crawl_run_id: ObjectId, limit: int | None = None) -> list[dict[str, Any]]:
    cursor = get_crawled_pages_collection().find(
        {"crawlRunId": crawl_run_id},
        sort=[("pageIndex", ASCENDING)],
    )

    if isinstance(limit, int) and limit > 0:
        cursor = cursor.limit(limit)

    return list(cursor)


def enrich_analysis_result_with_crawl_data(
    analysis_result: dict[str, Any] | None,
    crawl_run_document: dict[str, Any] | None,
    crawled_page_documents: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    result = repair_value(analysis_result or {})

    if not crawl_run_document:
        return result

    pages = crawled_page_documents or []
    result["crawlMeta"] = serialize_crawl_run(crawl_run_document)
    result["crawlPages"] = [serialize_crawled_page(document) for document in pages]

    if not isinstance(result.get("sourcePages"), list) or not result.get("sourcePages"):
        result["sourcePages"] = [build_source_page(document) for document in pages[:6]]

    return result


def strip_crawl_payload(analysis_result: dict[str, Any] | None) -> dict[str, Any]:
    cleaned_result = repair_value(analysis_result or {})
    if isinstance(cleaned_result, dict):
        cleaned_result.pop("crawlMeta", None)
        cleaned_result.pop("crawlPages", None)
    return cleaned_result


def build_crawl_pages_payload(crawl_pages: Any, source_pages: Any) -> list[dict[str, Any]]:
    if isinstance(crawl_pages, list) and crawl_pages:
        normalized_pages: list[dict[str, Any]] = []
        for item in crawl_pages:
            if isinstance(item, dict):
                normalized_pages.append(
                    {
                        "url": get_non_empty_string(item.get("url")),
                        "title": get_non_empty_string(item.get("title")),
                        "description": get_non_empty_string(item.get("description")),
                        "headings": normalize_string_list(item.get("headings")),
                        "pageType": get_non_empty_string(item.get("pageType")) or "general",
                        "fetchMode": get_non_empty_string(item.get("fetchMode")) or "static",
                        "statusCode": positive_int(item.get("statusCode"), 200),
                        "excerpt": get_non_empty_string(item.get("excerpt")),
                        "mainContent": get_non_empty_string(item.get("mainContent")) or get_non_empty_string(item.get("excerpt")),
                        "ctaTexts": normalize_string_list(item.get("ctaTexts")),
                        "valueProps": normalize_string_list(item.get("valueProps")),
                        "pricingSignals": normalize_string_list(item.get("pricingSignals")),
                        "faqItems": normalize_faq_items(item.get("faqItems")),
                        "forms": normalize_forms(item.get("forms")),
                        "entityLabels": normalize_string_list(item.get("entityLabels")),
                        "imageAlts": normalize_string_list(item.get("imageAlts")),
                        "logoCandidates": normalize_string_list(item.get("logoCandidates")),
                        "technologies": normalize_string_list(item.get("technologies")),
                        "currencies": normalize_string_list(item.get("currencies")),
                        "meta": normalize_string_map(item.get("meta")),
                    }
                )
        return [page for page in normalized_pages if page.get("url")]

    if not isinstance(source_pages, list):
        return []

    fallback_pages: list[dict[str, Any]] = []
    for item in source_pages:
        if not isinstance(item, dict):
            continue
        url = get_non_empty_string(item.get("url"))
        if not url:
            continue
        fallback_pages.append(
            {
                "url": url,
                "title": get_non_empty_string(item.get("title")),
                "description": get_non_empty_string(item.get("description")),
                "headings": normalize_string_list(item.get("headings")),
                "pageType": get_non_empty_string(item.get("pageType")) or "general",
                "fetchMode": get_non_empty_string(item.get("fetchMode")) or "unknown",
                "statusCode": 200,
                "excerpt": get_non_empty_string(item.get("excerpt")),
                "mainContent": get_non_empty_string(item.get("excerpt")),
                "ctaTexts": [],
                "valueProps": [],
                "pricingSignals": [],
                "faqItems": [],
                "forms": [],
                "entityLabels": [],
                "imageAlts": [],
                "logoCandidates": [],
                "technologies": [],
                "currencies": [],
                "meta": {},
            }
        )
    return fallback_pages


def build_crawled_page_document(
    crawl_run_id: ObjectId,
    website_id: ObjectId,
    page_index: int,
    page_payload: dict[str, Any],
    now,
) -> dict[str, Any]:
    url = get_non_empty_string(page_payload.get("url"))
    return {
        "schemaVersion": SCHEMA_VERSION,
        "crawlRunId": crawl_run_id,
        "websiteId": website_id,
        "pageIndex": page_index,
        "url": url,
        "normalizedUrl": canonicalize_page_url(url),
        "pageType": get_non_empty_string(page_payload.get("pageType")) or "general",
        "fetchMode": get_non_empty_string(page_payload.get("fetchMode")) or "static",
        "statusCode": positive_int(page_payload.get("statusCode"), 200),
        "title": get_non_empty_string(page_payload.get("title")),
        "description": get_non_empty_string(page_payload.get("description")),
        "headings": normalize_string_list(page_payload.get("headings"))[:16],
        "excerpt": get_non_empty_string(page_payload.get("excerpt")),
        "mainContent": get_non_empty_string(page_payload.get("mainContent")),
        "ctaTexts": normalize_string_list(page_payload.get("ctaTexts"))[:16],
        "valueProps": normalize_string_list(page_payload.get("valueProps"))[:16],
        "pricingSignals": normalize_string_list(page_payload.get("pricingSignals"))[:16],
        "faqItems": normalize_faq_items(page_payload.get("faqItems"))[:10],
        "forms": normalize_forms(page_payload.get("forms"))[:8],
        "entityLabels": normalize_string_list(page_payload.get("entityLabels"))[:16],
        "imageAlts": normalize_string_list(page_payload.get("imageAlts"))[:16],
        "logoCandidates": normalize_string_list(page_payload.get("logoCandidates"))[:12],
        "technologies": normalize_string_list(page_payload.get("technologies"))[:12],
        "currencies": normalize_string_list(page_payload.get("currencies"))[:8],
        "meta": normalize_string_map(page_payload.get("meta")),
        "createdAt": now,
    }


def serialize_crawl_run(crawl_run_document: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": get_non_empty_string(crawl_run_document.get("status")) or "completed",
        "fetchStrategy": get_non_empty_string(crawl_run_document.get("fetchStrategy")) or "unknown",
        "pageLimit": positive_int(crawl_run_document.get("pageLimit"), 0),
        "depthLimit": positive_int(crawl_run_document.get("depthLimit"), 0),
        "pagesVisited": positive_int(crawl_run_document.get("pagesVisited"), 0),
        "pagesSucceeded": positive_int(crawl_run_document.get("pagesSucceeded"), 0),
        "pagesFailed": positive_int(crawl_run_document.get("pagesFailed"), 0),
        "sitemapUrls": normalize_string_list(crawl_run_document.get("sitemapUrls")),
        "renderModes": normalize_string_list(crawl_run_document.get("renderModes")),
        "notes": normalize_string_list(crawl_run_document.get("notes")),
    }


def serialize_crawled_page(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "url": get_non_empty_string(document.get("url")),
        "title": get_non_empty_string(document.get("title")),
        "description": get_non_empty_string(document.get("description")),
        "headings": normalize_string_list(document.get("headings")),
        "pageType": get_non_empty_string(document.get("pageType")) or "general",
        "fetchMode": get_non_empty_string(document.get("fetchMode")) or "static",
        "statusCode": positive_int(document.get("statusCode"), 200),
        "excerpt": get_non_empty_string(document.get("excerpt")),
        "mainContent": get_non_empty_string(document.get("mainContent")),
        "ctaTexts": normalize_string_list(document.get("ctaTexts")),
        "valueProps": normalize_string_list(document.get("valueProps")),
        "pricingSignals": normalize_string_list(document.get("pricingSignals")),
        "faqItems": normalize_faq_items(document.get("faqItems")),
        "forms": normalize_forms(document.get("forms")),
        "entityLabels": normalize_string_list(document.get("entityLabels")),
        "imageAlts": normalize_string_list(document.get("imageAlts")),
        "logoCandidates": normalize_string_list(document.get("logoCandidates")),
        "technologies": normalize_string_list(document.get("technologies")),
        "currencies": normalize_string_list(document.get("currencies")),
        "meta": normalize_string_map(document.get("meta")),
    }


def build_source_page(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "url": get_non_empty_string(document.get("url")),
        "title": get_non_empty_string(document.get("title")),
        "description": get_non_empty_string(document.get("description")),
        "headings": normalize_string_list(document.get("headings"))[:8],
        "pageType": get_non_empty_string(document.get("pageType")) or "general",
        "fetchMode": get_non_empty_string(document.get("fetchMode")) or "static",
        "excerpt": get_non_empty_string(document.get("excerpt"))
        or get_non_empty_string(document.get("mainContent"))[:700],
    }


def canonicalize_page_url(url: str) -> str:
    if not url:
        return ""

    parsed = urlparse(url.strip())
    path = parsed.path or "/"
    return urlunparse(
        (
            parsed.scheme or "https",
            parsed.netloc.replace("www.", "").lower(),
            path.rstrip("/") or "/",
            "",
            "",
            "",
        )
    )


def normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def normalize_string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, str] = {}
    for key, item in value.items():
        if isinstance(key, str) and isinstance(item, str):
            clean_key = key.strip()
            clean_value = item.strip()
            if clean_key and clean_value:
                normalized[clean_key] = clean_value
    return normalized


def normalize_faq_items(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    items: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        question = get_non_empty_string(item.get("question"))
        answer = get_non_empty_string(item.get("answer"))
        if question or answer:
            items.append({"question": question, "answer": answer})
    return items


def normalize_forms(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    items: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "action": get_non_empty_string(item.get("action")),
                "method": get_non_empty_string(item.get("method")) or "GET",
                "fields": normalize_string_list(item.get("fields")),
            }
        )
    return items


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


def infer_fetch_strategy(render_modes: Iterable[str]) -> str:
    modes = {mode.strip().lower() for mode in render_modes if isinstance(mode, str) and mode.strip()}
    if "stealth" in modes:
        return "scrapling-stealth"
    if "dynamic" in modes:
        return "scrapling-dynamic"
    if "httpx-selector" in modes:
        return "httpx-selector-fallback"
    if "static" in modes:
        return "scrapling-static"
    return "unknown"


def unique_ordered(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)

    return result


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
