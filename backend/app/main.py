from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    AnalyzeRequest,
    AnalyzeResponse,
    AuditEventListResponseModel,
    WorkspaceSnapshotModel,
    WorkspaceSnapshotRequest,
)
from .services.analysis_enrichment import build_quality_review, build_strategic_summary
from .services.audit_store import list_recent_audit_events, serialize_audit_event, write_audit_event
from .services.auth import AuthenticatedUser, get_current_user
from .services.chat_store import build_ephemeral_chat_thread
from .services.fallback import (
    FALLBACK_ENGINE_VERSION,
    FALLBACK_PROMPT_VERSION,
    build_fallback_analysis,
)
from .services.gemini import GEMINI_PROMPT_VERSION, generate_analysis_with_gemini
from .services.integration_store import build_preview_integration_payload
from .services.memory_templates import normalize_memory_files
from .services.observability import configure_observability, duration_ms, log_structured, now_perf
from .services.scrape import crawl_website
from .services.user_store import ensure_user_indexes, get_user_by_identity
from .services.workspace_store import (
    ensure_indexes,
    get_active_workspace_context,
    get_workspace_snapshot,
    ping_database,
    save_workspace_snapshot,
)


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_observability()
    ensure_indexes()
    ensure_user_indexes()
    log_structured("app_startup", version="0.4.0")
    yield


app = FastAPI(
    title="Acrtech AI Marketer API",
    version="0.4.0",
    lifespan=lifespan,
)
frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex[:12]
    request.state.request_id = request_id
    started_at = now_perf()

    try:
        response = await call_next(request)
    except Exception as exc:
        log_structured(
            "http_request",
            level="error",
            requestId=request_id,
            method=request.method,
            path=request.url.path,
            query=str(request.url.query or ""),
            statusCode=500,
            durationMs=duration_ms(started_at),
            error=str(exc),
        )
        raise

    response.headers["X-Request-ID"] = request_id
    log_structured(
        "http_request",
        requestId=request_id,
        method=request.method,
        path=request.url.path,
        query=str(request.url.query or ""),
        statusCode=response.status_code,
        durationMs=duration_ms(started_at),
    )
    return response


def build_analysis_audit_payload(
    payload: AnalyzeRequest,
    analysis_meta: dict[str, str],
    *,
    crawl_duration_ms: int,
    synthesis_duration_ms: int,
    total_duration_ms: int,
    pages_visited: int,
    pages_succeeded: int,
    pages_failed: int,
    fetch_strategy: str,
    note_count: int,
) -> dict[str, object]:
    return {
        "website": payload.website,
        "goalCount": len(payload.goals),
        "connectedPlatformCount": len(payload.connected_platforms),
        "crawlDurationMs": crawl_duration_ms,
        "synthesisDurationMs": synthesis_duration_ms,
        "totalDurationMs": total_duration_ms,
        "engine": analysis_meta["engine"],
        "engineVersion": analysis_meta["engineVersion"],
        "promptVersion": analysis_meta["promptVersion"],
        "pagesVisited": pages_visited,
        "pagesSucceeded": pages_succeeded,
        "pagesFailed": pages_failed,
        "fetchStrategy": fetch_strategy,
        "noteCount": note_count,
    }


@app.get("/api/health")
def healthcheck() -> dict:
    database_ok = ping_database()
    return {
        "status": "ok" if database_ok else "degraded",
        "database": "ok" if database_ok else "unreachable",
        "version": "0.4.0",
    }


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_website(
    payload: AnalyzeRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AnalyzeResponse:
    request_id = getattr(request.state, "request_id", None)
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    user_document = get_user_by_identity(current_user.uid, current_user.email)
    operation_started_at = now_perf()
    crawl_started_at = now_perf()

    log_structured(
        "analysis_started",
        requestId=request_id,
        firebaseUid=current_user.uid,
        website=payload.website,
        goalCount=len(payload.goals),
        connectedPlatformCount=len(payload.connected_platforms),
    )

    try:
        bundle = await crawl_website(payload.website)
    except ValueError as exc:
        duration = duration_ms(operation_started_at)
        write_audit_event(
            event_type="analysis_failed",
            status="validation_error",
            entity_type="analysis_request",
            user_document=user_document,
            request_id=request_id,
            payload={
                "website": payload.website,
                "goalCount": len(payload.goals),
                "connectedPlatformCount": len(payload.connected_platforms),
                "durationMs": duration,
                "error": str(exc),
            },
        )
        log_structured(
            "analysis_failed",
            level="warning",
            requestId=request_id,
            firebaseUid=current_user.uid,
            website=payload.website,
            durationMs=duration,
            error=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        duration = duration_ms(operation_started_at)
        write_audit_event(
            event_type="analysis_failed",
            status="crawl_error",
            entity_type="analysis_request",
            user_document=user_document,
            request_id=request_id,
            payload={
                "website": payload.website,
                "goalCount": len(payload.goals),
                "connectedPlatformCount": len(payload.connected_platforms),
                "durationMs": duration,
                "error": str(exc),
            },
        )
        log_structured(
            "analysis_failed",
            level="error",
            requestId=request_id,
            firebaseUid=current_user.uid,
            website=payload.website,
            durationMs=duration,
            error=str(exc),
        )
        raise HTTPException(status_code=502, detail=f"Web sitesi taranırken hata oluştu: {exc}") from exc

    crawl_duration = duration_ms(crawl_started_at)
    gemini_error = None
    analysis_payload = None
    used_gemini = False
    synthesis_started_at = now_perf()

    try:
        analysis_payload = await generate_analysis_with_gemini(
            bundle,
            payload.goals,
            payload.connected_platforms,
        )
        used_gemini = bool(analysis_payload)
    except Exception as exc:
        gemini_error = f"Gemini analizi kullanılamadı, yedek akışa geçildi: {exc}"

    if not analysis_payload:
        analysis_payload = build_fallback_analysis(
            bundle,
            payload.goals,
            payload.connected_platforms,
        )

    analysis_payload.setdefault("analysis", {})
    strategic_summary = build_strategic_summary(bundle, analysis_payload, payload.goals)
    analysis_payload["strategicSummary"] = strategic_summary
    analysis_payload["memoryFiles"] = normalize_memory_files(
        analysis_payload.get("memoryFiles", []),
        bundle=bundle,
        analysis=analysis_payload["analysis"],
        goals=payload.goals,
        connected_platforms=payload.connected_platforms,
        strategic_summary=strategic_summary,
    )
    analysis_payload["qualityReview"] = build_quality_review(bundle, analysis_payload)

    synthesis_duration = duration_ms(synthesis_started_at)
    analysis_meta = (
        {
            "engine": "fallback",
            "engineVersion": FALLBACK_ENGINE_VERSION,
            "promptVersion": FALLBACK_PROMPT_VERSION,
        }
        if not used_gemini
        else {
            "engine": "gemini",
            "engineVersion": gemini_model,
            "promptVersion": GEMINI_PROMPT_VERSION,
        }
    )

    analysis_payload["analysis"]["logoUrl"] = bundle.site_signals.logo_url or None
    preview_integrations = build_preview_integration_payload(payload.connected_platforms)

    notes = list(bundle.notes)
    if gemini_error:
        notes.append(gemini_error)

    audit_payload = build_analysis_audit_payload(
        payload,
        analysis_meta,
        crawl_duration_ms=crawl_duration,
        synthesis_duration_ms=synthesis_duration,
        total_duration_ms=duration_ms(operation_started_at),
        pages_visited=bundle.crawl_meta.pages_visited,
        pages_succeeded=bundle.crawl_meta.pages_succeeded,
        pages_failed=bundle.crawl_meta.pages_failed,
        fetch_strategy=bundle.crawl_meta.fetch_strategy,
        note_count=len(notes[:8]),
    )
    write_audit_event(
        event_type="analysis_completed",
        status="success",
        entity_type="analysis_request",
        user_document=user_document,
        request_id=request_id,
        payload=audit_payload,
    )
    log_structured(
        "analysis_completed",
        requestId=request_id,
        firebaseUid=current_user.uid,
        **audit_payload,
    )

    return AnalyzeResponse.model_validate(
        {
            "analysis": analysis_payload["analysis"],
            "memoryFiles": analysis_payload["memoryFiles"],
            "sourcePages": [
                {
                    "url": page.url,
                    "title": page.title,
                    "description": page.description,
                    "headings": page.headings[:6],
                    "pageType": page.page_type,
                    "fetchMode": page.fetch_mode,
                    "excerpt": (page.main_content or page.excerpt)[:700],
                }
                for page in bundle.pages[:6]
            ],
            "researchPackage": {
                "companyNameCandidates": bundle.research_package.company_name_candidates,
                "heroMessages": bundle.research_package.hero_messages,
                "positioningSignals": bundle.research_package.positioning_signals,
                "offerSignals": bundle.research_package.offer_signals,
                "serviceOffers": bundle.research_package.service_offers,
                "productOffers": bundle.research_package.product_offers,
                "audienceSignals": bundle.research_package.audience_signals,
                "trustSignals": bundle.research_package.trust_signals,
                "proofPoints": bundle.research_package.proof_points,
                "conversionActions": bundle.research_package.conversion_actions,
                "contentTopics": bundle.research_package.content_topics,
                "seoSignals": bundle.research_package.seo_signals,
                "geographySignals": bundle.research_package.geography_signals,
                "languageSignals": bundle.research_package.language_signals,
                "marketSignals": bundle.research_package.market_signals,
                "visualSignals": bundle.research_package.visual_signals,
            },
            "strategicSummary": analysis_payload.get("strategicSummary"),
            "qualityReview": analysis_payload.get("qualityReview"),
            "crawlMeta": {
                "status": bundle.crawl_meta.status,
                "fetchStrategy": bundle.crawl_meta.fetch_strategy,
                "pageLimit": bundle.crawl_meta.page_limit,
                "depthLimit": bundle.crawl_meta.depth_limit,
                "pagesVisited": bundle.crawl_meta.pages_visited,
                "pagesSucceeded": bundle.crawl_meta.pages_succeeded,
                "pagesFailed": bundle.crawl_meta.pages_failed,
                "sitemapUrls": bundle.crawl_meta.sitemap_urls,
                "renderModes": bundle.crawl_meta.render_modes,
                "notes": bundle.crawl_meta.notes,
            },
            "crawlPages": [
                {
                    "url": page.url,
                    "title": page.title,
                    "description": page.description,
                    "headings": page.headings,
                    "pageType": page.page_type,
                    "fetchMode": page.fetch_mode,
                    "statusCode": page.status_code,
                    "excerpt": page.excerpt,
                    "mainContent": page.main_content,
                    "ctaTexts": page.cta_texts,
                    "valueProps": page.value_props,
                    "pricingSignals": page.pricing_signals,
                    "faqItems": [
                        {
                            "question": faq.question,
                            "answer": faq.answer,
                        }
                        for faq in page.faq_items
                    ],
                    "forms": [
                        {
                            "action": form.action,
                            "method": form.method,
                            "fields": form.fields,
                        }
                        for form in page.forms
                    ],
                    "entityLabels": page.entity_labels,
                    "imageAlts": page.image_alts,
                    "logoCandidates": page.logo_candidates,
                    "technologies": page.technologies,
                    "currencies": page.currencies,
                    "meta": page.meta,
                }
                for page in bundle.pages
            ],
            "notes": notes[:8],
            "contactSignals": {
                "emails": bundle.contact_signals.emails,
                "phones": bundle.contact_signals.phones,
                "socials": bundle.contact_signals.socials,
                "addresses": bundle.contact_signals.addresses,
            },
            "analysisMeta": analysis_meta,
            "integrationConnections": preview_integrations["integrationConnections"],
            "integrationSyncRuns": preview_integrations["integrationSyncRuns"],
            "chatThread": build_ephemeral_chat_thread(
                {
                    "analysis": analysis_payload["analysis"],
                    "memoryFiles": analysis_payload["memoryFiles"],
                    "sourcePages": [
                        {
                            "url": page.url,
                            "title": page.title,
                            "description": page.description,
                            "headings": page.headings[:6],
                            "pageType": page.page_type,
                            "fetchMode": page.fetch_mode,
                            "excerpt": (page.main_content or page.excerpt)[:700],
                        }
                        for page in bundle.pages[:6]
                    ],
                    "researchPackage": {
                        "companyNameCandidates": bundle.research_package.company_name_candidates,
                        "heroMessages": bundle.research_package.hero_messages,
                        "positioningSignals": bundle.research_package.positioning_signals,
                        "offerSignals": bundle.research_package.offer_signals,
                        "serviceOffers": bundle.research_package.service_offers,
                        "productOffers": bundle.research_package.product_offers,
                        "audienceSignals": bundle.research_package.audience_signals,
                        "trustSignals": bundle.research_package.trust_signals,
                        "proofPoints": bundle.research_package.proof_points,
                        "conversionActions": bundle.research_package.conversion_actions,
                        "contentTopics": bundle.research_package.content_topics,
                        "seoSignals": bundle.research_package.seo_signals,
                        "geographySignals": bundle.research_package.geography_signals,
                        "languageSignals": bundle.research_package.language_signals,
                        "marketSignals": bundle.research_package.market_signals,
                        "visualSignals": bundle.research_package.visual_signals,
                    },
                    "strategicSummary": analysis_payload.get("strategicSummary"),
                    "qualityReview": analysis_payload.get("qualityReview"),
                    "crawlMeta": {
                        "status": bundle.crawl_meta.status,
                        "fetchStrategy": bundle.crawl_meta.fetch_strategy,
                        "pageLimit": bundle.crawl_meta.page_limit,
                        "depthLimit": bundle.crawl_meta.depth_limit,
                        "pagesVisited": bundle.crawl_meta.pages_visited,
                        "pagesSucceeded": bundle.crawl_meta.pages_succeeded,
                        "pagesFailed": bundle.crawl_meta.pages_failed,
                        "sitemapUrls": bundle.crawl_meta.sitemap_urls,
                        "renderModes": bundle.crawl_meta.render_modes,
                        "notes": bundle.crawl_meta.notes,
                    },
                    "notes": notes[:8],
                    "contactSignals": {
                        "emails": bundle.contact_signals.emails,
                        "phones": bundle.contact_signals.phones,
                        "socials": bundle.contact_signals.socials,
                        "addresses": bundle.contact_signals.addresses,
                    },
                    "analysisMeta": analysis_meta,
                    "integrationConnections": preview_integrations["integrationConnections"],
                    "integrationSyncRuns": preview_integrations["integrationSyncRuns"],
                },
                specialist_id="aylin",
            ),
        }
    )


@app.get("/api/workspace-snapshot", response_model=WorkspaceSnapshotModel)
def read_workspace_snapshot(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> WorkspaceSnapshotModel:
    request_id = getattr(request.state, "request_id", None)
    context = get_active_workspace_context(current_user.uid, current_user.email)
    snapshot = get_workspace_snapshot(current_user.uid, current_user.email)

    if not snapshot:
        write_audit_event(
            event_type="workspace_snapshot_read",
            status="not_found",
            entity_type="workspace_snapshot",
            user_document=context.get("userDocument") if isinstance(context, dict) else None,
            workspace_document=context.get("workspaceDocument") if isinstance(context, dict) else None,
            website_document=context.get("websiteDocument") if isinstance(context, dict) else None,
            analysis_run_id=(
                context.get("analysisRunDocument", {}).get("_id")
                if isinstance(context, dict) and isinstance(context.get("analysisRunDocument"), dict)
                else None
            ),
            request_id=request_id,
            payload={
                "firebaseUid": current_user.uid,
                "hasWorkspace": bool(context and context.get("workspaceDocument")),
                "hasAnalysis": bool(context and context.get("analysisRunDocument")),
            },
        )
        log_structured(
            "workspace_snapshot_read",
            level="warning",
            requestId=request_id,
            firebaseUid=current_user.uid,
            status="not_found",
            hasWorkspace=bool(context and context.get("workspaceDocument")),
            hasAnalysis=bool(context and context.get("analysisRunDocument")),
        )
        raise HTTPException(status_code=404, detail="Workspace kaydı bulunamadı.")

    write_audit_event(
        event_type="workspace_snapshot_read",
        status="success",
        entity_type="workspace_snapshot",
        user_document=context.get("userDocument") if isinstance(context, dict) else None,
        workspace_document=context.get("workspaceDocument") if isinstance(context, dict) else None,
        website_document=context.get("websiteDocument") if isinstance(context, dict) else None,
        analysis_run_id=(
            context.get("analysisRunDocument", {}).get("_id")
            if isinstance(context, dict) and isinstance(context.get("analysisRunDocument"), dict)
            else None
        ),
        request_id=request_id,
        payload={
            "firebaseUid": current_user.uid,
            "website": snapshot.get("website", ""),
            "selectedGoalCount": len(snapshot.get("selectedGoals", [])),
            "connectedPlatformCount": len(snapshot.get("connectedPlatforms", [])),
        },
    )
    log_structured(
        "workspace_snapshot_read",
        requestId=request_id,
        firebaseUid=current_user.uid,
        status="success",
        website=snapshot.get("website", ""),
        selectedGoalCount=len(snapshot.get("selectedGoals", [])),
        connectedPlatformCount=len(snapshot.get("connectedPlatforms", [])),
    )
    return WorkspaceSnapshotModel.model_validate(snapshot)


@app.post("/api/workspace-snapshot")
def persist_workspace_snapshot(
    payload: WorkspaceSnapshotRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    request_id = getattr(request.state, "request_id", None)
    snapshot_data = payload.model_dump(by_alias=True)
    operation_started_at = now_perf()
    result = save_workspace_snapshot(current_user.uid, current_user.email, snapshot_data)
    duration = duration_ms(operation_started_at)

    write_audit_event(
        event_type="workspace_snapshot_persisted",
        status="success",
        entity_type="workspace_snapshot",
        entity_id=(
            result.get("workspaceDocument", {}).get("_id")
            if isinstance(result.get("workspaceDocument"), dict)
            else None
        ),
        user_document=result.get("userDocument") if isinstance(result, dict) else None,
        workspace_document=result.get("workspaceDocument") if isinstance(result, dict) else None,
        website_document=result.get("websiteDocument") if isinstance(result, dict) else None,
        analysis_run_id=result.get("analysisRunId") if isinstance(result, dict) else None,
        crawl_run_id=result.get("crawlRunId") if isinstance(result, dict) else None,
        thread_id=result.get("threadId") if isinstance(result, dict) else None,
        request_id=request_id,
        payload={
            "website": snapshot_data.get("website", ""),
            "selectedGoalCount": len(snapshot_data.get("selectedGoals", [])),
            "connectedPlatformCount": len(snapshot_data.get("connectedPlatforms", [])),
            "durationMs": duration,
        },
    )
    log_structured(
        "workspace_snapshot_persisted",
        requestId=request_id,
        firebaseUid=current_user.uid,
        website=snapshot_data.get("website", ""),
        selectedGoalCount=len(snapshot_data.get("selectedGoals", [])),
        connectedPlatformCount=len(snapshot_data.get("connectedPlatforms", [])),
        durationMs=duration,
        workspaceId=(
            str(result.get("workspaceDocument", {}).get("_id"))
            if isinstance(result.get("workspaceDocument"), dict)
            and result.get("workspaceDocument", {}).get("_id")
            else None
        ),
    )
    return {"status": "ok"}


@app.get("/api/ops/recent-events", response_model=AuditEventListResponseModel)
def read_recent_audit_events(
    limit: int = Query(default=20, ge=1, le=50),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuditEventListResponseModel:
    context = get_active_workspace_context(current_user.uid, current_user.email)
    workspace_document = (
        context.get("workspaceDocument")
        if isinstance(context, dict) and isinstance(context.get("workspaceDocument"), dict)
        else None
    )
    user_document = (
        context.get("userDocument")
        if isinstance(context, dict) and isinstance(context.get("userDocument"), dict)
        else get_user_by_identity(current_user.uid, current_user.email)
    )
    events = list_recent_audit_events(
        workspace_id=workspace_document.get("_id") if isinstance(workspace_document, dict) else None,
        user_id=user_document.get("_id") if isinstance(user_document, dict) else None,
        limit=limit,
    )
    return AuditEventListResponseModel.model_validate(
        {"events": [serialize_audit_event(document) for document in events]}
    )
