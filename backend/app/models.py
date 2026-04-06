from pydantic import BaseModel, ConfigDict, Field


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    website: str
    goals: list[str] = Field(default_factory=list)
    connected_platforms: list[str] = Field(
        default_factory=list,
        alias="connectedPlatforms",
    )


class BrandAssetsResponseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    brand_logo: str | None = Field(default=None, alias="brandLogo")
    favicon: str | None = None
    touch_icon: str | None = Field(default=None, alias="touchIcon")
    social_image: str | None = Field(default=None, alias="socialImage")
    manifest_url: str | None = Field(default=None, alias="manifestUrl")
    mask_icon: str | None = Field(default=None, alias="maskIcon")
    tile_image: str | None = Field(default=None, alias="tileImage")
    candidates: list[str] = Field(default_factory=list)


class AnalysisResponseModel(BaseModel):
    company_name: str = Field(alias="companyName")
    domain: str
    logo_url: str | None = Field(default=None, alias="logoUrl")
    brand_assets: BrandAssetsResponseModel | None = Field(default=None, alias="brandAssets")
    sector: str
    offer: str
    audience: str
    tone: str
    price_position: str = Field(alias="pricePosition")
    competitors: list[str]
    opportunity: str
    first_month_plan: list[str] = Field(alias="firstMonthPlan")
    palette: list[str]


class MemoryFileResponseModel(BaseModel):
    id: str
    filename: str
    title: str
    blurb: str
    content: str
    version: int | None = None
    is_current: bool | None = Field(default=None, alias="isCurrent")


class FaqItemResponseModel(BaseModel):
    question: str
    answer: str


class FormResponseModel(BaseModel):
    action: str
    method: str
    fields: list[str] = Field(default_factory=list)


class SourcePageResponseModel(BaseModel):
    url: str
    title: str
    description: str
    headings: list[str]
    page_type: str = Field(alias="pageType")
    fetch_mode: str = Field(alias="fetchMode")
    excerpt: str


class CrawlPageResponseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    url: str
    title: str
    description: str
    headings: list[str] = Field(default_factory=list)
    page_type: str = Field(alias="pageType")
    fetch_mode: str = Field(alias="fetchMode")
    status_code: int = Field(alias="statusCode")
    excerpt: str
    main_content: str = Field(alias="mainContent")
    cta_texts: list[str] = Field(default_factory=list, alias="ctaTexts")
    value_props: list[str] = Field(default_factory=list, alias="valueProps")
    pricing_signals: list[str] = Field(default_factory=list, alias="pricingSignals")
    faq_items: list[FaqItemResponseModel] = Field(default_factory=list, alias="faqItems")
    forms: list[FormResponseModel] = Field(default_factory=list)
    entity_labels: list[str] = Field(default_factory=list, alias="entityLabels")
    image_alts: list[str] = Field(default_factory=list, alias="imageAlts")
    logo_candidates: list[str] = Field(default_factory=list, alias="logoCandidates")
    technologies: list[str] = Field(default_factory=list)
    currencies: list[str] = Field(default_factory=list)
    zones: dict[str, list[str]] = Field(default_factory=dict)
    meta: dict[str, str] = Field(default_factory=dict)


class CrawlMetaResponseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    fetch_strategy: str = Field(alias="fetchStrategy")
    page_limit: int = Field(alias="pageLimit")
    depth_limit: int = Field(alias="depthLimit")
    pages_visited: int = Field(alias="pagesVisited")
    pages_succeeded: int = Field(alias="pagesSucceeded")
    pages_failed: int = Field(alias="pagesFailed")
    sitemap_urls: list[str] = Field(default_factory=list, alias="sitemapUrls")
    render_modes: list[str] = Field(default_factory=list, alias="renderModes")
    notes: list[str] = Field(default_factory=list)


class ContactSignalsResponseModel(BaseModel):
    emails: list[str]
    phones: list[str]
    socials: list[str]
    addresses: list[str] = Field(default_factory=list)


class ResearchPackageResponseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    company_name_candidates: list[str] = Field(default_factory=list, alias="companyNameCandidates")
    hero_messages: list[str] = Field(default_factory=list, alias="heroMessages")
    semantic_zones: dict[str, list[str]] = Field(default_factory=dict, alias="semanticZones")
    positioning_signals: list[str] = Field(default_factory=list, alias="positioningSignals")
    offer_signals: list[str] = Field(default_factory=list, alias="offerSignals")
    service_offers: list[str] = Field(default_factory=list, alias="serviceOffers")
    product_offers: list[str] = Field(default_factory=list, alias="productOffers")
    audience_signals: list[str] = Field(default_factory=list, alias="audienceSignals")
    trust_signals: list[str] = Field(default_factory=list, alias="trustSignals")
    proof_points: list[str] = Field(default_factory=list, alias="proofPoints")
    conversion_actions: list[str] = Field(default_factory=list, alias="conversionActions")
    content_topics: list[str] = Field(default_factory=list, alias="contentTopics")
    seo_signals: list[str] = Field(default_factory=list, alias="seoSignals")
    geography_signals: list[str] = Field(default_factory=list, alias="geographySignals")
    language_signals: list[str] = Field(default_factory=list, alias="languageSignals")
    market_signals: list[str] = Field(default_factory=list, alias="marketSignals")
    visual_signals: list[str] = Field(default_factory=list, alias="visualSignals")
    core_value_props: list[str] = Field(default_factory=list, alias="coreValueProps")
    supporting_benefits: list[str] = Field(default_factory=list, alias="supportingBenefits")
    proof_claims: list[str] = Field(default_factory=list, alias="proofClaims")
    audience_claims: list[str] = Field(default_factory=list, alias="audienceClaims")
    cta_claims: list[str] = Field(default_factory=list, alias="ctaClaims")
    evidence_blocks: list[dict[str, object]] = Field(default_factory=list, alias="evidenceBlocks")


class StrategicSummaryResponseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    positioning: str
    differentiation: str
    best_fit_audience: str = Field(alias="bestFitAudience")
    primary_growth_lever: str = Field(alias="primaryGrowthLever")
    conversion_gap: str = Field(alias="conversionGap")
    content_angle: str = Field(alias="contentAngle")


class QualityCheckResponseModel(BaseModel):
    id: str
    label: str
    passed: bool
    detail: str


class QualityReviewResponseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    score: int
    verdict: str
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    checks: list[QualityCheckResponseModel] = Field(default_factory=list)


class AnalysisMetaResponseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    engine: str
    engine_version: str = Field(alias="engineVersion")
    prompt_version: str = Field(alias="promptVersion")


class IntegrationConnectionResponseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    provider_key: str = Field(alias="providerKey")
    provider: str
    status: str
    account_label: str = Field(default="", alias="accountLabel")
    scopes: list[str] = Field(default_factory=list)
    auth_mode: str = Field(default="selection_only", alias="authMode")
    token_configured: bool = Field(default=False, alias="tokenConfigured")
    last_sync_status: str = Field(default="", alias="lastSyncStatus")
    last_sync_message: str = Field(default="", alias="lastSyncMessage")
    last_sync_at: str | None = Field(default=None, alias="lastSyncAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")


class IntegrationSyncRunResponseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    provider_key: str = Field(alias="providerKey")
    provider: str
    status: str
    trigger: str
    message: str
    started_at: str | None = Field(default=None, alias="startedAt")
    finished_at: str | None = Field(default=None, alias="finishedAt")


class ChatAttachmentResponseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: str
    id: str
    file_id: str = Field(default="", alias="fileId")
    filename: str = ""
    title: str = ""
    blurb: str = ""
    version: int | None = None
    is_current: bool | None = Field(default=None, alias="isCurrent")


class ChatMessageResponseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    sender_type: str = Field(alias="senderType")
    sender_id: str = Field(alias="senderId")
    message_type: str = Field(alias="messageType")
    content: str
    attachments: list[ChatAttachmentResponseModel] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
    related_analysis_run_id: str | None = Field(default=None, alias="relatedAnalysisRunId")
    created_at: str | None = Field(default=None, alias="createdAt")


class ChatThreadResponseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    status: str
    messages: list[ChatMessageResponseModel] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    analysis: AnalysisResponseModel
    memory_files: list[MemoryFileResponseModel] = Field(alias="memoryFiles")
    source_pages: list[SourcePageResponseModel] = Field(alias="sourcePages")
    research_package: ResearchPackageResponseModel | None = Field(default=None, alias="researchPackage")
    strategic_summary: StrategicSummaryResponseModel | None = Field(default=None, alias="strategicSummary")
    quality_review: QualityReviewResponseModel | None = Field(default=None, alias="qualityReview")
    notes: list[str]
    contact_signals: ContactSignalsResponseModel = Field(alias="contactSignals")
    analysis_meta: AnalysisMetaResponseModel | None = Field(default=None, alias="analysisMeta")
    crawl_meta: CrawlMetaResponseModel | None = Field(default=None, alias="crawlMeta")
    crawl_pages: list[CrawlPageResponseModel] = Field(default_factory=list, alias="crawlPages")
    integration_connections: list[IntegrationConnectionResponseModel] = Field(
        default_factory=list,
        alias="integrationConnections",
    )
    integration_sync_runs: list[IntegrationSyncRunResponseModel] = Field(
        default_factory=list,
        alias="integrationSyncRuns",
    )
    chat_thread: ChatThreadResponseModel | None = Field(default=None, alias="chatThread")


class WorkspaceSnapshotModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    website: str
    selected_goals: list[str] = Field(default_factory=list, alias="selectedGoals")
    connected_platforms: list[str] = Field(
        default_factory=list,
        alias="connectedPlatforms",
    )
    analysis_result: AnalyzeResponse = Field(alias="analysisResult")
    trial_activated: bool = Field(default=False, alias="trialActivated")
    selected_specialist: str = Field(default="aylin", alias="selectedSpecialist")


class WorkspaceSnapshotRequest(WorkspaceSnapshotModel):
    pass


class ChatMessageRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    chat_thread: ChatThreadResponseModel = Field(alias="chatThread")
    remaining_user_messages: int = Field(alias="remainingUserMessages")
    max_user_messages: int = Field(alias="maxUserMessages")


class AuditEventResponseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    event_type: str = Field(alias="eventType")
    status: str
    entity_type: str = Field(alias="entityType")
    entity_id: str | None = Field(default=None, alias="entityId")
    workspace_id: str | None = Field(default=None, alias="workspaceId")
    website_id: str | None = Field(default=None, alias="websiteId")
    user_id: str | None = Field(default=None, alias="userId")
    request_id: str | None = Field(default=None, alias="requestId")
    payload: dict[str, object] = Field(default_factory=dict)
    created_at: str | None = Field(default=None, alias="createdAt")


class AuditEventListResponseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    events: list[AuditEventResponseModel] = Field(default_factory=list)
