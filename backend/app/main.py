from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    AnalyzeRequest,
    AnalyzeResponse,
    AuditEventListResponseModel,
    ChatMessageRequest,
    ChatMessageResponse,
    GuestSessionClaimResponseModel,
    GuestSessionResponseModel,
    WorkspaceSnapshotModel,
    WorkspaceSnapshotRequest,
)
from .services.analysis_enrichment import build_quality_review, build_strategic_summary
from .services.audit_store import list_recent_audit_events, serialize_audit_event, write_audit_event
from .services.auth import AuthenticatedUser, get_current_user
from .services.chat_store import (
    CHAT_USER_MESSAGE_LIMIT,
    append_chat_exchange,
    build_ephemeral_chat_thread,
    count_user_messages_for_thread,
    ensure_workspace_thread,
    get_latest_thread_for_workspace,
    get_messages_for_thread,
    serialize_chat_thread,
)
from .services.guest_store import (
    attach_workspace_to_guest_session,
    claim_guest_session_to_user,
    create_guest_session,
    ensure_guest_indexes,
    ensure_guest_session,
    get_guest_user_document,
)
from .services.fallback import (
    FALLBACK_ENGINE_VERSION,
    FALLBACK_PROMPT_VERSION,
    build_fallback_analysis,
)
from .services.gemini import (
    GEMINI_CHAT_PROMPT_VERSION,
    GEMINI_PROMPT_VERSION,
    build_fallback_chat_reply,
    generate_analysis_with_gemini,
    generate_chat_reply_with_gemini,
)
from .services.integration_store import build_preview_integration_payload
from .services.memory_templates import normalize_memory_files
from .services.observability import configure_observability, duration_ms, log_structured, now_perf
from .services.output_normalizer import normalize_analysis_payload_language
from .services.scrape import crawl_website
from .services.database import utc_now
from .services.user_store import ensure_user_indexes, get_user_by_identity
from .services.workspace_store import (
    ensure_indexes,
    get_active_workspace_context,
    get_workspaces_collection,
    get_workspace_snapshot,
    ping_database,
    save_workspace_snapshot,
)


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_observability()
    try:
        ensure_indexes()
        ensure_user_indexes()
        ensure_guest_indexes()
    except Exception as exc:  # pragma: no cover - production startup resilience
        log_structured(
            "database_startup_warning",
            level="error",
            error=str(exc),
        )
    log_structured("app_startup", version="0.4.0")
    yield


app = FastAPI(
    title="Acrtech AI Marketer API",
    version="0.4.0",
    lifespan=lifespan,
)
frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173")
frontend_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", frontend_origin).split(",")
    if origin.strip()
]
frontend_origins.extend(
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://ai-marketer-hhto.vercel.app",
    ]
)
GUEST_SESSION_HEADER = "X-Guest-Session-ID"

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(frontend_origins)),
    allow_origin_regex=r"https://.*\.vercel\.app",
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


def read_guest_session_id(request: Request) -> str:
    session_id = request.headers.get(GUEST_SESSION_HEADER, "").strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="Misafir oturumu bulunamadı.")
    return session_id


def build_analyze_response_payload(
    *,
    bundle,
    analysis_payload: dict,
    analysis_meta: dict[str, str],
    notes: list[str],
    preview_integrations: dict[str, list[dict]],
) -> dict:
    return {
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
            "semanticZones": bundle.research_package.semantic_zones,
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
            "coreValueProps": bundle.research_package.core_value_props,
            "supportingBenefits": bundle.research_package.supporting_benefits,
            "proofClaims": bundle.research_package.proof_claims,
            "audienceClaims": bundle.research_package.audience_claims,
            "ctaClaims": bundle.research_package.cta_claims,
            "evidenceBlocks": bundle.research_package.evidence_blocks,
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
                "zones": page.zones,
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
                    "semanticZones": bundle.research_package.semantic_zones,
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
                    "coreValueProps": bundle.research_package.core_value_props,
                    "supportingBenefits": bundle.research_package.supporting_benefits,
                    "proofClaims": bundle.research_package.proof_claims,
                    "audienceClaims": bundle.research_package.audience_claims,
                    "ctaClaims": bundle.research_package.cta_claims,
                    "evidenceBlocks": bundle.research_package.evidence_blocks,
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


@app.get("/api/health")
def healthcheck() -> dict:
    database_ok = ping_database()
    return {
        "status": "ok" if database_ok else "degraded",
        "database": "ok" if database_ok else "unreachable",
        "version": "0.4.0",
    }


async def run_analysis_request(
    *,
    payload: AnalyzeRequest,
    request_id: str | None,
    actor_id: str,
    user_document: dict | None,
) -> dict:
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    operation_started_at = now_perf()
    crawl_started_at = now_perf()

    log_structured(
        "analysis_started",
        requestId=request_id,
        actorId=actor_id,
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
            actorId=actor_id,
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
            actorId=actor_id,
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

    analysis_payload = normalize_analysis_payload_language(analysis_payload)

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
    analysis_payload["analysis"]["brandAssets"] = {
        "brandLogo": bundle.site_signals.brand_assets.brand_logo or None,
        "favicon": bundle.site_signals.brand_assets.favicon or None,
        "touchIcon": bundle.site_signals.brand_assets.touch_icon or None,
        "socialImage": bundle.site_signals.brand_assets.social_image or None,
        "manifestUrl": bundle.site_signals.brand_assets.manifest_url or None,
        "maskIcon": bundle.site_signals.brand_assets.mask_icon or None,
        "tileImage": bundle.site_signals.brand_assets.tile_image or None,
        "candidates": bundle.site_signals.brand_assets.candidates[:16],
    }
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
        actorId=actor_id,
        **audit_payload,
    )

    return build_analyze_response_payload(
        bundle=bundle,
        analysis_payload=analysis_payload,
        analysis_meta=analysis_meta,
        notes=notes,
        preview_integrations=preview_integrations,
    )


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_website(
    payload: AnalyzeRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AnalyzeResponse:
    request_id = getattr(request.state, "request_id", None)
    user_document = get_user_by_identity(current_user.uid, current_user.email)
    response_payload = await run_analysis_request(
        payload=payload,
        request_id=request_id,
        actor_id=current_user.uid,
        user_document=user_document,
    )
    return AnalyzeResponse.model_validate(response_payload)


@app.post("/api/guest-session", response_model=GuestSessionResponseModel)
def create_guest_session_endpoint() -> GuestSessionResponseModel:
    session_document = create_guest_session()
    return GuestSessionResponseModel.model_validate(
        {
            "guestSessionId": session_document["sessionId"],
            "status": session_document.get("status", "active"),
        }
    )


@app.post("/api/analyze-guest", response_model=AnalyzeResponse)
async def analyze_guest_website(
    payload: AnalyzeRequest,
    request: Request,
) -> AnalyzeResponse:
    request_id = getattr(request.state, "request_id", None)
    guest_session_id = read_guest_session_id(request)
    session_document = ensure_guest_session(guest_session_id)
    guest_user_document = get_guest_user_document(guest_session_id)
    if not guest_user_document:
        raise HTTPException(status_code=404, detail="Misafir oturumu bulunamadı.")

    response_payload = await run_analysis_request(
        payload=payload,
        request_id=request_id,
        actor_id=session_document.get("guestFirebaseUid", f"guest:{guest_session_id}"),
        user_document=guest_user_document,
    )

    snapshot_payload = {
        "website": payload.website,
        "selectedGoals": payload.goals,
        "connectedPlatforms": payload.connected_platforms,
        "analysisResult": response_payload,
        "trialActivated": False,
        "selectedSpecialist": "aylin",
    }
    persist_result = save_workspace_snapshot(
        session_document.get("guestFirebaseUid", f"guest:{guest_session_id}"),
        None,
        snapshot_payload,
    )
    workspace_document = persist_result.get("workspaceDocument", {})
    workspace_id = workspace_document.get("_id")
    if isinstance(workspace_id, ObjectId):
        attach_workspace_to_guest_session(guest_session_id, workspace_id)

    return AnalyzeResponse.model_validate(response_payload)


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


@app.get("/api/workspace-snapshot-guest", response_model=WorkspaceSnapshotModel)
def read_guest_workspace_snapshot(request: Request) -> WorkspaceSnapshotModel:
    request_id = getattr(request.state, "request_id", None)
    guest_session_id = read_guest_session_id(request)
    session_document = ensure_guest_session(guest_session_id)
    guest_firebase_uid = session_document.get("guestFirebaseUid", f"guest:{guest_session_id}")
    snapshot = get_workspace_snapshot(guest_firebase_uid, None)
    context = get_active_workspace_context(guest_firebase_uid, None)

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
              "guestSessionId": guest_session_id,
              "hasWorkspace": bool(context and context.get("workspaceDocument")),
              "hasAnalysis": bool(context and context.get("analysisRunDocument")),
          },
      )
      raise HTTPException(status_code=404, detail="Misafir çalışma alanı bulunamadı.")

    return WorkspaceSnapshotModel.model_validate(snapshot)


@app.post("/api/guest-session/claim", response_model=GuestSessionClaimResponseModel)
def claim_guest_session(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> GuestSessionClaimResponseModel:
    guest_session_id = read_guest_session_id(request)
    user_document = get_user_by_identity(current_user.uid, current_user.email)
    if not user_document:
        raise HTTPException(status_code=404, detail="Kullanıcı kaydı bulunamadı.")

    claimed_workspace_id = claim_guest_session_to_user(guest_session_id, user_document)
    return GuestSessionClaimResponseModel.model_validate(
        {
            "status": "claimed",
            "claimedWorkspaceId": str(claimed_workspace_id) if claimed_workspace_id else None,
        }
    )


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


@app.post("/api/chat-message", response_model=ChatMessageResponse)
async def send_chat_message(
    payload: ChatMessageRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ChatMessageResponse:
    request_id = getattr(request.state, "request_id", None)
    message_text = payload.message.strip()

    if not message_text:
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz.")

    context = get_active_workspace_context(current_user.uid, current_user.email)
    if not context or not isinstance(context.get("workspaceDocument"), dict):
        raise HTTPException(status_code=404, detail="Aktif çalışma alanı bulunamadı.")
    if not isinstance(context.get("analysisRunDocument"), dict):
        raise HTTPException(status_code=404, detail="Önce bir analiz oluşturmanız gerekiyor.")
    if not isinstance(context.get("userDocument"), dict):
        raise HTTPException(status_code=404, detail="Kullanıcı kaydı bulunamadı.")

    workspace_document = context["workspaceDocument"]
    analysis_run_document = context["analysisRunDocument"]
    user_document = context["userDocument"]
    specialist_id = str(workspace_document.get("selectedSpecialist") or "aylin")
    now = utc_now()

    workspace_snapshot = get_workspace_snapshot(current_user.uid, current_user.email)
    if not workspace_snapshot:
        raise HTTPException(status_code=404, detail="Çalışma alanı verisi bulunamadı.")

    thread_document = get_latest_thread_for_workspace(workspace_document)
    if not thread_document:
        thread_document = ensure_workspace_thread(
            workspace_document=workspace_document,
            user_document=user_document,
            analysis_result=workspace_snapshot.get("analysisResult", {}),
            now=now,
        )
        get_workspaces_collection().update_one(
            {"_id": workspace_document["_id"]},
            {
                "$set": {
                    "latestThreadId": thread_document["_id"],
                    "updatedAt": now,
                }
            },
        )

    user_message_count = count_user_messages_for_thread(thread_document["_id"])
    if user_message_count >= CHAT_USER_MESSAGE_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Bu oturum için maksimum {CHAT_USER_MESSAGE_LIMIT} mesaj hakkı doldu.",
        )

    message_documents = get_messages_for_thread(thread_document["_id"], limit=24)
    assistant_reply = None
    used_gemini_chat = False
    try:
        assistant_reply = await generate_chat_reply_with_gemini(
            workspace_snapshot=workspace_snapshot,
            recent_messages=message_documents,
            user_message=message_text,
        )
        used_gemini_chat = bool(assistant_reply)
    except Exception as exc:
        log_structured(
            "chat_reply_fallback",
            level="warning",
            requestId=request_id,
            firebaseUid=current_user.uid,
            workspaceId=str(workspace_document["_id"]),
            error=str(exc),
        )

    if not assistant_reply:
        assistant_reply = build_fallback_chat_reply(
            workspace_snapshot=workspace_snapshot,
            user_message=message_text,
        )

    updated_messages = append_chat_exchange(
        thread_document=thread_document,
        workspace_document=workspace_document,
        user_document=user_document,
        user_message=message_text,
        assistant_message=assistant_reply,
        specialist_id=specialist_id,
        related_analysis_run_id=analysis_run_document.get("_id"),
        now=now,
    )
    refreshed_thread = get_latest_thread_for_workspace(workspace_document) or thread_document
    total_user_messages = count_user_messages_for_thread(thread_document["_id"])
    remaining_user_messages = max(CHAT_USER_MESSAGE_LIMIT - total_user_messages, 0)

    write_audit_event(
        event_type="chat_message_sent",
        status="success",
        entity_type="chat_thread",
        entity_id=thread_document.get("_id"),
        user_document=user_document,
        workspace_document=workspace_document,
        website_document=context.get("websiteDocument") if isinstance(context.get("websiteDocument"), dict) else None,
        analysis_run_id=analysis_run_document.get("_id"),
        thread_id=thread_document.get("_id"),
        request_id=request_id,
        payload={
            "messageLength": len(message_text),
            "remainingUserMessages": remaining_user_messages,
            "maxUserMessages": CHAT_USER_MESSAGE_LIMIT,
            "promptVersion": GEMINI_CHAT_PROMPT_VERSION if used_gemini_chat else "fallback-chat-v1",
        },
    )
    log_structured(
        "chat_message_sent",
        requestId=request_id,
        firebaseUid=current_user.uid,
        workspaceId=str(workspace_document["_id"]),
        threadId=str(thread_document["_id"]),
        remainingUserMessages=remaining_user_messages,
        maxUserMessages=CHAT_USER_MESSAGE_LIMIT,
    )

    return ChatMessageResponse.model_validate(
        {
            "chatThread": serialize_chat_thread(refreshed_thread, updated_messages),
            "remainingUserMessages": remaining_user_messages,
            "maxUserMessages": CHAT_USER_MESSAGE_LIMIT,
        }
    )


@app.post("/api/chat-message-guest", response_model=ChatMessageResponse)
async def send_guest_chat_message(
    payload: ChatMessageRequest,
    request: Request,
) -> ChatMessageResponse:
    request_id = getattr(request.state, "request_id", None)
    message_text = payload.message.strip()

    if not message_text:
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz.")

    guest_session_id = read_guest_session_id(request)
    session_document = ensure_guest_session(guest_session_id)
    guest_firebase_uid = session_document.get("guestFirebaseUid", f"guest:{guest_session_id}")
    context = get_active_workspace_context(guest_firebase_uid, None)
    if not context or not isinstance(context.get("workspaceDocument"), dict):
        raise HTTPException(status_code=404, detail="Aktif misafir çalışma alanı bulunamadı.")
    if not isinstance(context.get("analysisRunDocument"), dict):
        raise HTTPException(status_code=404, detail="Önce bir analiz oluşturmanız gerekiyor.")
    if not isinstance(context.get("userDocument"), dict):
        raise HTTPException(status_code=404, detail="Misafir kullanıcı kaydı bulunamadı.")

    workspace_document = context["workspaceDocument"]
    analysis_run_document = context["analysisRunDocument"]
    user_document = context["userDocument"]
    specialist_id = str(workspace_document.get("selectedSpecialist") or "aylin")
    now = utc_now()

    workspace_snapshot = get_workspace_snapshot(guest_firebase_uid, None)
    if not workspace_snapshot:
        raise HTTPException(status_code=404, detail="Misafir çalışma alanı verisi bulunamadı.")

    thread_document = get_latest_thread_for_workspace(workspace_document)
    if not thread_document:
        thread_document = ensure_workspace_thread(
            workspace_document=workspace_document,
            user_document=user_document,
            analysis_result=workspace_snapshot.get("analysisResult", {}),
            now=now,
        )
        get_workspaces_collection().update_one(
            {"_id": workspace_document["_id"]},
            {
                "$set": {
                    "latestThreadId": thread_document["_id"],
                    "updatedAt": now,
                }
            },
        )

    user_message_count = count_user_messages_for_thread(thread_document["_id"])
    if user_message_count >= CHAT_USER_MESSAGE_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Bu oturum için maksimum {CHAT_USER_MESSAGE_LIMIT} mesaj hakkı doldu.",
        )

    message_documents = get_messages_for_thread(thread_document["_id"], limit=24)
    assistant_reply = None
    used_gemini_chat = False
    try:
        assistant_reply = await generate_chat_reply_with_gemini(
            workspace_snapshot=workspace_snapshot,
            recent_messages=message_documents,
            user_message=message_text,
        )
        used_gemini_chat = bool(assistant_reply)
    except Exception as exc:
        log_structured(
            "chat_reply_fallback",
            level="warning",
            requestId=request_id,
            guestSessionId=guest_session_id,
            workspaceId=str(workspace_document["_id"]),
            error=str(exc),
        )

    if not assistant_reply:
        assistant_reply = build_fallback_chat_reply(
            workspace_snapshot=workspace_snapshot,
            user_message=message_text,
        )

    updated_messages = append_chat_exchange(
        thread_document=thread_document,
        workspace_document=workspace_document,
        user_document=user_document,
        user_message=message_text,
        assistant_message=assistant_reply,
        specialist_id=specialist_id,
        related_analysis_run_id=analysis_run_document.get("_id"),
        now=now,
    )
    refreshed_thread = get_latest_thread_for_workspace(workspace_document) or thread_document
    total_user_messages = count_user_messages_for_thread(thread_document["_id"])
    remaining_user_messages = max(CHAT_USER_MESSAGE_LIMIT - total_user_messages, 0)

    write_audit_event(
        event_type="chat_message_sent",
        status="success",
        entity_type="chat_thread",
        entity_id=thread_document.get("_id"),
        user_document=user_document,
        workspace_document=workspace_document,
        website_document=context.get("websiteDocument") if isinstance(context.get("websiteDocument"), dict) else None,
        analysis_run_id=analysis_run_document.get("_id"),
        thread_id=thread_document.get("_id"),
        request_id=request_id,
        payload={
            "messageLength": len(message_text),
            "remainingUserMessages": remaining_user_messages,
            "maxUserMessages": CHAT_USER_MESSAGE_LIMIT,
            "promptVersion": GEMINI_CHAT_PROMPT_VERSION if used_gemini_chat else "fallback-chat-v1",
            "guestSessionId": guest_session_id,
        },
    )
    log_structured(
        "chat_message_sent",
        requestId=request_id,
        guestSessionId=guest_session_id,
        workspaceId=str(workspace_document["_id"]),
        threadId=str(thread_document["_id"]),
        remainingUserMessages=remaining_user_messages,
        maxUserMessages=CHAT_USER_MESSAGE_LIMIT,
    )

    return ChatMessageResponse.model_validate(
        {
            "chatThread": serialize_chat_thread(refreshed_thread, updated_messages),
            "remainingUserMessages": remaining_user_messages,
            "maxUserMessages": CHAT_USER_MESSAGE_LIMIT,
        }
    )


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
