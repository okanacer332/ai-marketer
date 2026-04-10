import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import {
  createUserWithEmailAndPassword,
  fetchSignInMethodsForEmail,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
  updateProfile,
  type User,
} from 'firebase/auth'
import './App.css'
import {
  buildAnalysis,
  capabilityTags,
  goalOptions,
  normalizeWebsite,
  platformOptions,
  specialists,
  type Step,
} from './appData'
import { RevolutLanding } from './components/landing/RevolutLanding'
import {
  analyzeWebsite,
  analyzeGuestWebsite,
  claimGuestWorkspace,
  createGuestSession,
  fetchWorkspaceSnapshot,
  fetchGuestWorkspaceSnapshot,
  sendChatMessage,
  sendGuestChatMessage,
  storeWorkspaceSnapshot,
} from './lib/api'
import { auth, firebaseInitError, firebaseReady, googleProvider } from './lib/firebase'
import type {
  AnalyzeResponse,
  Analysis,
  AnalysisMeta,
  BrandAssets,
  ChatAttachment,
  ChatMessage,
  ChatMessageResponse,
  ChatThread,
  ContactSignals,
  CrawlForm,
  CrawlMeta,
  CrawlPage,
  FaqItem,
  IntegrationConnection,
  IntegrationSyncRun,
  MemoryFile,
  QualityCheck,
  QualityReview,
  ResearchPackage,
  SourcePage,
  StrategicSummary,
  WorkspaceSnapshot,
} from './types'

type AuthMode = 'signup' | 'signin'

const WORKSPACE_SNAPSHOT_PREFIX = 'acrtech-workspace:'
const WORKSPACE_EMAIL_SNAPSHOT_PREFIX = 'acrtech-workspace-email:'
const GUEST_SESSION_STORAGE_KEY = 'olric-guest-session-id'
const CHAT_MESSAGE_LIMIT = 10
const DEFAULT_GOALS = ['SEO', 'Sosyal Medya', 'Ücretli Reklamlar']
const EMPTY_CRAWL_META: CrawlMeta = {
  status: 'completed',
  fetchStrategy: 'unknown',
  pageLimit: 0,
  depthLimit: 0,
  pagesVisited: 0,
  pagesSucceeded: 0,
  pagesFailed: 0,
  sitemapUrls: [],
  renderModes: [],
  notes: [],
}

const STEP_PATHS: Record<Exclude<Step, 'signup'>, string> = {
  specialist: '/',
  website: '/basla',
  goals: '/hedefler',
  integrations: '/baglantilar',
  workspace: '/calisma-alani',
}

function getStepFromPathname(pathname: string): Step {
  const normalizedPath = pathname.replace(/\/+$/, '') || '/'

  const matchedEntry = Object.entries(STEP_PATHS).find(([, path]) => path === normalizedPath)

  if (!matchedEntry) {
    return 'specialist'
  }

  return matchedEntry[0] as Step
}

function purgeLegacyWorkspaceStorage() {
  if (typeof window === 'undefined') {
    return
  }

  try {
    const keysToRemove: string[] = []

    for (let index = 0; index < window.localStorage.length; index += 1) {
      const key = window.localStorage.key(index)

      if (
        key?.startsWith(WORKSPACE_SNAPSHOT_PREFIX) ||
        key?.startsWith(WORKSPACE_EMAIL_SNAPSHOT_PREFIX)
      ) {
        keysToRemove.push(key)
      }
    }

    keysToRemove.forEach((key) => window.localStorage.removeItem(key))
  } catch {
    // Ignore storage errors so the main flow keeps working.
  }
}

function readStoredGuestSessionId() {
  if (typeof window === 'undefined') {
    return ''
  }

  try {
    return window.localStorage.getItem(GUEST_SESSION_STORAGE_KEY) || ''
  } catch {
    return ''
  }
}

function writeStoredGuestSessionId(sessionId: string) {
  if (typeof window === 'undefined') {
    return
  }

  try {
    if (sessionId.trim()) {
      window.localStorage.setItem(GUEST_SESSION_STORAGE_KEY, sessionId.trim())
    } else {
      window.localStorage.removeItem(GUEST_SESSION_STORAGE_KEY)
    }
  } catch {
    // Ignore storage errors so guest flow can continue in-memory.
  }
}

function normalizeStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

function normalizeStringRecord(value: unknown): Record<string, string> {
  if (!value || typeof value !== 'object') {
    return {}
  }

  return Object.entries(value).reduce<Record<string, string>>((result, [key, item]) => {
    if (typeof item === 'string') {
      result[key] = item
    }

    return result
  }, {})
}

function normalizeUnknownRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object') {
    return {}
  }

  return Object.entries(value).reduce<Record<string, unknown>>((result, [key, item]) => {
    result[key] = item
    return result
  }, {})
}

function normalizeContactSignals(value: Partial<ContactSignals> | null | undefined): ContactSignals {
  return {
    emails: normalizeStringArray(value?.emails),
    phones: normalizeStringArray(value?.phones),
    socials: normalizeStringArray(value?.socials),
    addresses: normalizeStringArray(value?.addresses),
  }
}

function normalizeBrandAssets(value: Partial<BrandAssets> | null | undefined): BrandAssets | null {
  if (!value) {
    return null
  }

  const normalized: BrandAssets = {
    brandLogo: typeof value.brandLogo === 'string' ? value.brandLogo : null,
    favicon: typeof value.favicon === 'string' ? value.favicon : null,
    touchIcon: typeof value.touchIcon === 'string' ? value.touchIcon : null,
    socialImage: typeof value.socialImage === 'string' ? value.socialImage : null,
    manifestUrl: typeof value.manifestUrl === 'string' ? value.manifestUrl : null,
    maskIcon: typeof value.maskIcon === 'string' ? value.maskIcon : null,
    tileImage: typeof value.tileImage === 'string' ? value.tileImage : null,
    candidates: normalizeStringArray(value.candidates),
  }

  const hasAnyAsset = [
    normalized.brandLogo,
    normalized.favicon,
    normalized.touchIcon,
    normalized.socialImage,
    normalized.manifestUrl,
    normalized.maskIcon,
    normalized.tileImage,
    ...normalized.candidates,
  ].some(Boolean)

  return hasAnyAsset ? normalized : null
}

function normalizeResearchPackage(
  value: Partial<ResearchPackage> | null | undefined,
): ResearchPackage | null {
  if (!value) {
    return null
  }

  return {
    companyNameCandidates: normalizeStringArray(value.companyNameCandidates),
    heroMessages: normalizeStringArray(value.heroMessages),
    semanticZones: Object.entries(normalizeUnknownRecord(value.semanticZones)).reduce<
      Record<string, string[]>
    >((result, [key, item]) => {
      result[key] = normalizeStringArray(item)
      return result
    }, {}),
    positioningSignals: normalizeStringArray(value.positioningSignals),
    offerSignals: normalizeStringArray(value.offerSignals),
    serviceOffers: normalizeStringArray(value.serviceOffers),
    productOffers: normalizeStringArray(value.productOffers),
    audienceSignals: normalizeStringArray(value.audienceSignals),
    trustSignals: normalizeStringArray(value.trustSignals),
    proofPoints: normalizeStringArray(value.proofPoints),
    conversionActions: normalizeStringArray(value.conversionActions),
    contentTopics: normalizeStringArray(value.contentTopics),
    seoSignals: normalizeStringArray(value.seoSignals),
    geographySignals: normalizeStringArray(value.geographySignals),
    languageSignals: normalizeStringArray(value.languageSignals),
    marketSignals: normalizeStringArray(value.marketSignals),
    visualSignals: normalizeStringArray(value.visualSignals),
    coreValueProps: normalizeStringArray(value.coreValueProps),
    supportingBenefits: normalizeStringArray(value.supportingBenefits),
    proofClaims: normalizeStringArray(value.proofClaims),
    audienceClaims: normalizeStringArray(value.audienceClaims),
    ctaClaims: normalizeStringArray(value.ctaClaims),
    evidenceBlocks: Array.isArray(value.evidenceBlocks)
      ? value.evidenceBlocks
          .filter((item) => Boolean(item && typeof item === 'object'))
          .map((item) => {
            const normalizedItem = normalizeUnknownRecord(item)
            return {
              type: typeof normalizedItem.type === 'string' ? normalizedItem.type : 'signal',
              claim: typeof normalizedItem.claim === 'string' ? normalizedItem.claim : '',
              why: typeof normalizedItem.why === 'string' ? normalizedItem.why : '',
              confidence: typeof normalizedItem.confidence === 'number' ? normalizedItem.confidence : 0,
              evidenceUrls: normalizeStringArray(normalizedItem.evidenceUrls),
            }
          })
          .filter((item) => Boolean(item.claim))
      : [],
  }
}

function normalizeStrategicSummary(
  value: Partial<StrategicSummary> | null | undefined,
): StrategicSummary | null {
  if (
    !value ||
    typeof value.positioning !== 'string' ||
    typeof value.differentiation !== 'string' ||
    typeof value.bestFitAudience !== 'string' ||
    typeof value.primaryGrowthLever !== 'string' ||
    typeof value.conversionGap !== 'string' ||
    typeof value.contentAngle !== 'string'
  ) {
    return null
  }

  return {
    positioning: value.positioning,
    differentiation: value.differentiation,
    bestFitAudience: value.bestFitAudience,
    primaryGrowthLever: value.primaryGrowthLever,
    conversionGap: value.conversionGap,
    contentAngle: value.contentAngle,
  }
}

function normalizeQualityChecks(value: unknown): QualityCheck[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value
    .filter((item): item is Partial<QualityCheck> => Boolean(item && typeof item === 'object'))
    .map((item, index) => ({
      id: typeof item.id === 'string' ? item.id : `quality-check-${index + 1}`,
      label: typeof item.label === 'string' ? item.label : `Kontrol ${index + 1}`,
      passed: Boolean(item.passed),
      detail: typeof item.detail === 'string' ? item.detail : '',
    }))
}

function normalizeQualityReview(
  value: Partial<QualityReview> | null | undefined,
): QualityReview | null {
  if (!value || typeof value.score !== 'number' || typeof value.verdict !== 'string') {
    return null
  }

  return {
    score: value.score,
    verdict: value.verdict,
    strengths: normalizeStringArray(value.strengths),
    risks: normalizeStringArray(value.risks),
    checks: normalizeQualityChecks(value.checks),
  }
}

function normalizeMemoryFiles(value: unknown): MemoryFile[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value
    .filter((item): item is Partial<MemoryFile> => Boolean(item && typeof item === 'object'))
    .map((item, index) => ({
      id: typeof item.id === 'string' ? item.id : `memory-${index + 1}`,
      filename: typeof item.filename === 'string' ? item.filename : `memory-${index + 1}.md`,
      title: typeof item.title === 'string' ? item.title : `Dosya ${index + 1}`,
      blurb: typeof item.blurb === 'string' ? item.blurb : '',
      content: typeof item.content === 'string' ? item.content : '',
      version: typeof item.version === 'number' ? item.version : null,
      isCurrent: typeof item.isCurrent === 'boolean' ? item.isCurrent : null,
    }))
}

function normalizeAnalysisMeta(value: Partial<AnalysisMeta> | null | undefined): AnalysisMeta | null {
  if (
    !value ||
    typeof value.engine !== 'string' ||
    typeof value.engineVersion !== 'string' ||
    typeof value.promptVersion !== 'string'
  ) {
    return null
  }

  return {
    engine: value.engine,
    engineVersion: value.engineVersion,
    promptVersion: value.promptVersion,
  }
}

function normalizeIntegrationConnections(value: unknown): IntegrationConnection[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value
    .filter((item): item is Partial<IntegrationConnection> => Boolean(item && typeof item === 'object'))
    .map((item, index) => ({
      id: typeof item.id === 'string' ? item.id : `integration-${index + 1}`,
      providerKey:
        typeof item.providerKey === 'string' ? item.providerKey : `integration-${index + 1}`,
      provider: typeof item.provider === 'string' ? item.provider : 'Platform',
      status: typeof item.status === 'string' ? item.status : 'pending',
      accountLabel: typeof item.accountLabel === 'string' ? item.accountLabel : '',
      scopes: normalizeStringArray(item.scopes),
      authMode: typeof item.authMode === 'string' ? item.authMode : 'selection_only',
      tokenConfigured: Boolean(item.tokenConfigured),
      lastSyncStatus: typeof item.lastSyncStatus === 'string' ? item.lastSyncStatus : '',
      lastSyncMessage: typeof item.lastSyncMessage === 'string' ? item.lastSyncMessage : '',
      lastSyncAt: typeof item.lastSyncAt === 'string' ? item.lastSyncAt : null,
      updatedAt: typeof item.updatedAt === 'string' ? item.updatedAt : null,
    }))
}

function normalizeIntegrationSyncRuns(value: unknown): IntegrationSyncRun[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value
    .filter((item): item is Partial<IntegrationSyncRun> => Boolean(item && typeof item === 'object'))
    .map((item, index) => ({
      id: typeof item.id === 'string' ? item.id : `integration-sync-${index + 1}`,
      providerKey:
        typeof item.providerKey === 'string' ? item.providerKey : `integration-sync-${index + 1}`,
      provider: typeof item.provider === 'string' ? item.provider : 'Platform',
      status: typeof item.status === 'string' ? item.status : 'queued',
      trigger: typeof item.trigger === 'string' ? item.trigger : 'workspace_selection',
      message: typeof item.message === 'string' ? item.message : '',
      startedAt: typeof item.startedAt === 'string' ? item.startedAt : null,
      finishedAt: typeof item.finishedAt === 'string' ? item.finishedAt : null,
    }))
}

function normalizeChatAttachments(value: unknown): ChatAttachment[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value
    .filter((item): item is Partial<ChatAttachment> => Boolean(item && typeof item === 'object'))
    .map((item) => ({
      type: typeof item.type === 'string' ? item.type : 'memory_document',
      id: typeof item.id === 'string' ? item.id : '',
      fileId: typeof item.fileId === 'string' ? item.fileId : '',
      filename: typeof item.filename === 'string' ? item.filename : '',
      title: typeof item.title === 'string' ? item.title : '',
      blurb: typeof item.blurb === 'string' ? item.blurb : '',
      version: typeof item.version === 'number' ? item.version : null,
      isCurrent: typeof item.isCurrent === 'boolean' ? item.isCurrent : null,
    }))
    .filter((item) => Boolean(item.id || item.fileId || item.filename))
}

function normalizeChatMessages(value: unknown): ChatMessage[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value
    .filter((item): item is Partial<ChatMessage> => Boolean(item && typeof item === 'object'))
    .map((item, index) => ({
      id: typeof item.id === 'string' ? item.id : `message-${index + 1}`,
      senderType: typeof item.senderType === 'string' ? item.senderType : 'assistant',
      senderId: typeof item.senderId === 'string' ? item.senderId : 'aylin',
      messageType: typeof item.messageType === 'string' ? item.messageType : 'assistant_text',
      content: typeof item.content === 'string' ? item.content : '',
      attachments: normalizeChatAttachments(item.attachments),
      metadata: normalizeUnknownRecord(item.metadata),
      relatedAnalysisRunId:
        typeof item.relatedAnalysisRunId === 'string' ? item.relatedAnalysisRunId : null,
      createdAt: typeof item.createdAt === 'string' ? item.createdAt : null,
    }))
}

function normalizeChatThread(value: Partial<ChatThread> | null | undefined): ChatThread | null {
  if (!value || typeof value.id !== 'string' || typeof value.title !== 'string') {
    return null
  }

  return {
    id: value.id,
    title: value.title,
    status: typeof value.status === 'string' ? value.status : 'active',
    messages: normalizeChatMessages(value.messages),
  }
}

function normalizeSourcePages(value: unknown): SourcePage[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value
    .filter((item): item is Partial<SourcePage> => Boolean(item && typeof item === 'object'))
    .map((item) => ({
      url: typeof item.url === 'string' ? item.url : '',
      title: typeof item.title === 'string' ? item.title : '',
      description: typeof item.description === 'string' ? item.description : '',
      headings: normalizeStringArray(item.headings),
      pageType: typeof item.pageType === 'string' ? item.pageType : 'general',
      fetchMode: typeof item.fetchMode === 'string' ? item.fetchMode : 'static',
      excerpt: typeof item.excerpt === 'string' ? item.excerpt : '',
    }))
    .filter((item) => Boolean(item.url))
}

function normalizeFaqItems(value: unknown): FaqItem[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value
    .filter((item): item is Partial<FaqItem> => Boolean(item && typeof item === 'object'))
    .map((item) => ({
      question: typeof item.question === 'string' ? item.question : '',
      answer: typeof item.answer === 'string' ? item.answer : '',
    }))
    .filter((item) => Boolean(item.question || item.answer))
}

function normalizeCrawlForms(value: unknown): CrawlForm[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value
    .filter((item): item is Partial<CrawlForm> => Boolean(item && typeof item === 'object'))
    .map((item) => ({
      action: typeof item.action === 'string' ? item.action : '',
      method: typeof item.method === 'string' ? item.method : 'GET',
      fields: normalizeStringArray(item.fields),
    }))
}

function normalizeCrawlPages(value: unknown): CrawlPage[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value
    .filter((item): item is Partial<CrawlPage> => Boolean(item && typeof item === 'object'))
    .map((item) => ({
      url: typeof item.url === 'string' ? item.url : '',
      title: typeof item.title === 'string' ? item.title : '',
      description: typeof item.description === 'string' ? item.description : '',
      headings: normalizeStringArray(item.headings),
      pageType: typeof item.pageType === 'string' ? item.pageType : 'general',
      fetchMode: typeof item.fetchMode === 'string' ? item.fetchMode : 'static',
      statusCode: typeof item.statusCode === 'number' ? item.statusCode : 200,
      excerpt: typeof item.excerpt === 'string' ? item.excerpt : '',
      mainContent: typeof item.mainContent === 'string' ? item.mainContent : '',
      ctaTexts: normalizeStringArray(item.ctaTexts),
      valueProps: normalizeStringArray(item.valueProps),
      pricingSignals: normalizeStringArray(item.pricingSignals),
      faqItems: normalizeFaqItems(item.faqItems),
      forms: normalizeCrawlForms(item.forms),
      entityLabels: normalizeStringArray(item.entityLabels),
      imageAlts: normalizeStringArray(item.imageAlts),
      logoCandidates: normalizeStringArray(item.logoCandidates),
      technologies: normalizeStringArray(item.technologies),
      currencies: normalizeStringArray(item.currencies),
      zones: Object.entries(normalizeUnknownRecord(item.zones)).reduce<Record<string, string[]>>(
        (result, [key, zoneValue]) => {
          result[key] = normalizeStringArray(zoneValue)
          return result
        },
        {},
      ),
      meta: normalizeStringRecord(item.meta),
    }))
    .filter((item) => Boolean(item.url))
}

function normalizeCrawlMeta(value: Partial<CrawlMeta> | null | undefined): CrawlMeta {
  return {
    status: typeof value?.status === 'string' ? value.status : EMPTY_CRAWL_META.status,
    fetchStrategy:
      typeof value?.fetchStrategy === 'string' ? value.fetchStrategy : EMPTY_CRAWL_META.fetchStrategy,
    pageLimit: typeof value?.pageLimit === 'number' ? value.pageLimit : EMPTY_CRAWL_META.pageLimit,
    depthLimit: typeof value?.depthLimit === 'number' ? value.depthLimit : EMPTY_CRAWL_META.depthLimit,
    pagesVisited:
      typeof value?.pagesVisited === 'number' ? value.pagesVisited : EMPTY_CRAWL_META.pagesVisited,
    pagesSucceeded:
      typeof value?.pagesSucceeded === 'number' ? value.pagesSucceeded : EMPTY_CRAWL_META.pagesSucceeded,
    pagesFailed:
      typeof value?.pagesFailed === 'number' ? value.pagesFailed : EMPTY_CRAWL_META.pagesFailed,
    sitemapUrls: normalizeStringArray(value?.sitemapUrls),
    renderModes: normalizeStringArray(value?.renderModes),
    notes: normalizeStringArray(value?.notes),
  }
}

function normalizeAnalysis(value: Partial<Analysis> | null | undefined): Analysis | null {
  if (
    !value ||
    typeof value.companyName !== 'string' ||
    typeof value.domain !== 'string' ||
    typeof value.sector !== 'string' ||
    typeof value.offer !== 'string' ||
    typeof value.audience !== 'string' ||
    typeof value.tone !== 'string' ||
    typeof value.pricePosition !== 'string'
  ) {
    return null
  }

  return {
    companyName: value.companyName,
    domain: value.domain,
    logoUrl: typeof value.logoUrl === 'string' ? value.logoUrl : null,
    brandAssets: normalizeBrandAssets(value.brandAssets),
    sector: value.sector,
    offer: value.offer,
    audience: value.audience,
    tone: value.tone,
    pricePosition: value.pricePosition,
    competitors: normalizeStringArray(value.competitors),
    opportunity: typeof value.opportunity === 'string' ? value.opportunity : '',
    firstMonthPlan: normalizeStringArray(value.firstMonthPlan),
    palette: normalizeStringArray(value.palette),
  }
}

function normalizeAnalyzeResponse(value: Partial<AnalyzeResponse> | null | undefined): AnalyzeResponse | null {
  const normalizedAnalysis = normalizeAnalysis(value?.analysis)
  if (!normalizedAnalysis || !value) {
    return null
  }

  return {
    analysis: normalizedAnalysis,
    memoryFiles: normalizeMemoryFiles(value.memoryFiles),
    sourcePages: normalizeSourcePages(value.sourcePages),
    researchPackage: normalizeResearchPackage(value.researchPackage),
    strategicSummary: normalizeStrategicSummary(value.strategicSummary),
    qualityReview: normalizeQualityReview(value.qualityReview),
    analysisMeta: normalizeAnalysisMeta(value.analysisMeta),
    crawlMeta: normalizeCrawlMeta(value.crawlMeta),
    crawlPages: normalizeCrawlPages(value.crawlPages),
    integrationConnections: normalizeIntegrationConnections(value.integrationConnections),
    integrationSyncRuns: normalizeIntegrationSyncRuns(value.integrationSyncRuns),
    chatThread: normalizeChatThread(value.chatThread),
    notes: normalizeStringArray(value.notes),
    contactSignals: normalizeContactSignals(value.contactSignals),
  }
}

function normalizeWorkspaceSnapshot(snapshot: Partial<WorkspaceSnapshot> | null | undefined): WorkspaceSnapshot | null {
  if (!snapshot || typeof snapshot.website !== 'string') {
    return null
  }

  const analysisResult = normalizeAnalyzeResponse(snapshot.analysisResult)
  if (!analysisResult) {
    return null
  }

  return {
    website: snapshot.website,
    selectedGoals: normalizeStringArray(snapshot.selectedGoals),
    connectedPlatforms: normalizeStringArray(snapshot.connectedPlatforms),
    analysisResult,
    trialActivated: Boolean(snapshot.trialActivated),
    selectedSpecialist:
      typeof snapshot.selectedSpecialist === 'string' ? snapshot.selectedSpecialist : 'aylin',
  }
}

function buildPersistableSnapshot(snapshot: WorkspaceSnapshot): WorkspaceSnapshot {
  return {
    ...snapshot,
    analysisResult: {
      ...snapshot.analysisResult,
      chatThread: null,
    },
  }
}

function normalizeChatMessageResponse(
  value: Partial<ChatMessageResponse> | null | undefined,
): ChatMessageResponse | null {
  const normalizedChatThread = normalizeChatThread(value?.chatThread)
  if (
    !normalizedChatThread ||
    !value ||
    typeof value.remainingUserMessages !== 'number' ||
    typeof value.maxUserMessages !== 'number'
  ) {
    return null
  }

  return {
    chatThread: normalizedChatThread,
    remainingUserMessages: value.remainingUserMessages,
    maxUserMessages: value.maxUserMessages,
  }
}

async function readWorkspaceSnapshot(
): Promise<WorkspaceSnapshot | null> {
  try {
    return normalizeWorkspaceSnapshot(await fetchWorkspaceSnapshot())
  } catch {
    return null
  }
}

async function readGuestWorkspaceSnapshot(
  guestSessionId: string,
): Promise<WorkspaceSnapshot | null> {
  try {
    return normalizeWorkspaceSnapshot(await fetchGuestWorkspaceSnapshot(guestSessionId))
  } catch {
    return null
  }
}

async function writeWorkspaceSnapshot(
  snapshot: WorkspaceSnapshot,
) {
  const normalizedSnapshot = normalizeWorkspaceSnapshot(buildPersistableSnapshot(snapshot))
  if (!normalizedSnapshot) {
    return
  }

  await storeWorkspaceSnapshot(normalizedSnapshot).catch(() => null)
}

function buildSnapshotSignature(snapshot: WorkspaceSnapshot): string {
  return JSON.stringify(buildPersistableSnapshot(snapshot))
}

function App() {
  const [step, setStep] = useState<Step>(() =>
    typeof window === 'undefined' ? 'specialist' : getStepFromPathname(window.location.pathname),
  )
  const [selectedSpecialist, setSelectedSpecialist] = useState('aylin')
  const [authMode, setAuthMode] = useState<AuthMode>('signup')
  const [currentUser, setCurrentUser] = useState<User | null>(null)
  const [guestSessionId, setGuestSessionId] = useState(() => readStoredGuestSessionId())
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [website, setWebsite] = useState('')
  const [selectedGoals, setSelectedGoals] = useState<string[]>(DEFAULT_GOALS)
  const [connectedPlatforms, setConnectedPlatforms] = useState<string[]>([])
  const [analysisPhase, setAnalysisPhase] = useState(0)
  const [activeFileId, setActiveFileId] = useState<string | null>(null)
  const [trialActivated, setTrialActivated] = useState(false)
  const [authPending, setAuthPending] = useState(false)
  const [authDialogOpen, setAuthDialogOpen] = useState(false)
  const [analysisPending, setAnalysisPending] = useState(false)
  const [chatPending, setChatPending] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const [chatError, setChatError] = useState<string | null>(null)
  const [chatDraft, setChatDraft] = useState('')
  const [chatRemainingMessages, setChatRemainingMessages] = useState(CHAT_MESSAGE_LIMIT)
  const [pendingChatMessage, setPendingChatMessage] = useState<string | null>(null)
  const [analysisResult, setAnalysisResult] = useState<AnalyzeResponse | null>(null)
  const analysisRunRef = useRef(0)
  const hasAutoRestoredWorkspaceRef = useRef(false)
  const suppressAutoRestoreRef = useRef(false)
  const lastPersistedSnapshotRef = useRef<string | null>(null)

  const currentSpecialist =
    specialists.find((specialist) => specialist.id === selectedSpecialist) ||
    specialists[0]
  const previewAnalysis = buildAnalysis(website, selectedGoals, connectedPlatforms)
  const analysis = analysisResult?.analysis ?? previewAnalysis
  const memoryFiles = analysisResult?.memoryFiles ?? []
  const strategicSummary = analysisResult?.strategicSummary ?? null
  const qualityReview = analysisResult?.qualityReview ?? null
  const chatThread = analysisResult?.chatThread ?? null
  const activeFile = memoryFiles.find((file) => file.id === activeFileId) || null
  const isWorkspace = step === 'workspace'

  function openAuthDialog(mode: AuthMode = 'signin') {
    setAuthMode(mode)
    setAuthError(firebaseReady ? null : firebaseInitError || 'Giriş şu an kullanılamıyor.')
    setAuthDialogOpen(true)
  }

  function closeAuthDialog() {
    if (authPending) {
      return
    }

    setAuthDialogOpen(false)
  }

  async function ensureGuestSessionId() {
    if (guestSessionId.trim()) {
      return guestSessionId.trim()
    }

    const session = await createGuestSession()
    const nextSessionId = session.guestSessionId.trim()
    setGuestSessionId(nextSessionId)
    writeStoredGuestSessionId(nextSessionId)
    return nextSessionId
  }

  async function claimGuestWorkspaceIfNeeded() {
    const activeGuestSessionId = guestSessionId.trim()
    if (!activeGuestSessionId) {
      return
    }

    try {
      await claimGuestWorkspace(activeGuestSessionId)
      setGuestSessionId('')
      writeStoredGuestSessionId('')
    } catch {
      // Keep guest session if claim fails so the workspace is not lost.
    }
  }

  const restoreWorkspace = useCallback((snapshot: WorkspaceSnapshot) => {
    const normalizedSnapshot = normalizeWorkspaceSnapshot(snapshot)
    if (!normalizedSnapshot) {
      return
    }

    analysisRunRef.current += 1
    suppressAutoRestoreRef.current = false
    lastPersistedSnapshotRef.current = buildSnapshotSignature(normalizedSnapshot)
    setSelectedSpecialist(normalizedSnapshot.selectedSpecialist)
    setWebsite(normalizedSnapshot.website)
    setSelectedGoals(
      normalizedSnapshot.selectedGoals.length > 0
        ? normalizedSnapshot.selectedGoals
        : DEFAULT_GOALS,
    )
    setConnectedPlatforms(normalizedSnapshot.connectedPlatforms)
    setAnalysisResult(normalizedSnapshot.analysisResult)
    setAnalysisError(null)
    setChatError(null)
    setChatDraft('')
    setChatPending(false)
    setPendingChatMessage(null)
    setAnalysisPending(false)
    setAnalysisPhase(7)
    setTrialActivated(normalizedSnapshot.trialActivated)
    setActiveFileId(null)
    setChatRemainingMessages(
      Math.max(
        CHAT_MESSAGE_LIMIT -
          (normalizedSnapshot.analysisResult.chatThread?.messages.filter(
            (message) => message.senderType === 'user' && message.messageType === 'user_text',
          ).length || 0),
        0,
      ),
    )
    moveToStep('workspace')
  }, [])

  useEffect(() => {
    purgeLegacyWorkspaceStorage()
  }, [])

  useEffect(() => {
    const nextPath = step === 'signup' ? STEP_PATHS.specialist : STEP_PATHS[step]

    if (!nextPath || typeof window === 'undefined') {
      return
    }

    const currentPath = window.location.pathname || '/'

    if (currentPath !== nextPath) {
      window.history.replaceState({}, '', nextPath)
    }
  }, [step])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    const handlePopState = () => {
      setStep(getStepFromPathname(window.location.pathname))
    }

    window.addEventListener('popstate', handlePopState)

    return () => {
      window.removeEventListener('popstate', handlePopState)
    }
  }, [])

  useEffect(() => {
    if (!auth) {
      setCurrentUser(null)
      return
    }

    const unsubscribe = onAuthStateChanged(auth, (user) => {
      setCurrentUser(user)
      hasAutoRestoredWorkspaceRef.current = false
    })

    return () => {
      unsubscribe()
    }
  }, [])

  useEffect(() => {
    if (step !== 'workspace' || !analysisPending) {
      return
    }

    const timers = [900, 1800, 3000].map((delay, index) =>
      window.setTimeout(() => {
        setAnalysisPhase((current) => Math.max(current, index + 2))
      }, delay),
    )

    return () => {
      timers.forEach((timer) => window.clearTimeout(timer))
    }
  }, [step, analysisPending])

  useEffect(() => {
    if (step !== 'workspace' || analysisPending || !analysisResult || analysisError) {
      return
    }

    const timers = [450, 1000, 1600].map((delay, index) =>
      window.setTimeout(() => {
        setAnalysisPhase((current) => Math.max(current, index + 5))
      }, delay),
    )

    return () => {
      timers.forEach((timer) => window.clearTimeout(timer))
    }
  }, [step, analysisPending, analysisResult, analysisError])

  useEffect(() => {
    if (!currentUser || !analysisResult) {
      return
    }

    const snapshot = normalizeWorkspaceSnapshot({
      website,
      selectedGoals,
      connectedPlatforms,
      analysisResult,
      trialActivated,
      selectedSpecialist,
    })
    if (!snapshot) {
      return
    }

    const signature = buildSnapshotSignature(snapshot)
    if (lastPersistedSnapshotRef.current === signature) {
      return
    }

    lastPersistedSnapshotRef.current = signature
    void writeWorkspaceSnapshot(snapshot)
  }, [
    analysisResult,
    connectedPlatforms,
    currentUser,
    selectedGoals,
    selectedSpecialist,
    trialActivated,
    website,
  ])

  useEffect(() => {
    const userMessageCount =
      analysisResult?.chatThread?.messages.filter(
        (message) => message.senderType === 'user' && message.messageType === 'user_text',
      ).length || 0

    setChatRemainingMessages(Math.max(CHAT_MESSAGE_LIMIT - userMessageCount, 0))
  }, [analysisResult?.chatThread])

  useEffect(() => {
    if (
      !currentUser ||
      isWorkspace ||
      suppressAutoRestoreRef.current ||
      hasAutoRestoredWorkspaceRef.current
    ) {
      return
    }

    let cancelled = false

    void (async () => {
      const snapshot = await readWorkspaceSnapshot()

      if (!snapshot || cancelled) {
        return
      }

      hasAutoRestoredWorkspaceRef.current = true
      restoreWorkspace(snapshot)
    })()

    return () => {
      cancelled = true
    }
  }, [currentUser, isWorkspace, restoreWorkspace])

  useEffect(() => {
    if (
      currentUser ||
      !guestSessionId.trim() ||
      isWorkspace ||
      suppressAutoRestoreRef.current ||
      hasAutoRestoredWorkspaceRef.current
    ) {
      return
    }

    let cancelled = false

    void (async () => {
      const snapshot = await readGuestWorkspaceSnapshot(guestSessionId)

      if (!snapshot || cancelled) {
        return
      }

      hasAutoRestoredWorkspaceRef.current = true
      restoreWorkspace(snapshot)
    })()

    return () => {
      cancelled = true
    }
  }, [currentUser, guestSessionId, isWorkspace, restoreWorkspace])

  function moveToStep(nextStep: Step) {
    setStep(nextStep)
  }

  function invalidateAnalysisRun() {
    analysisRunRef.current += 1
    setAnalysisPending(false)
    setChatPending(false)
    setPendingChatMessage(null)
  }

  function handleBack() {
    if (step === 'signup') {
      setStep('specialist')
      return
    }

    if (step === 'website') {
      setStep('specialist')
      return
    }

    if (step === 'goals') {
      setStep('website')
      return
    }

    if (step === 'integrations') {
      setStep('goals')
      return
    }

    if (step === 'workspace') {
      invalidateAnalysisRun()
      setStep('integrations')
    }
  }

  function handleGoalToggle(goalLabel: string) {
    setSelectedGoals((currentGoals) => {
      if (currentGoals.includes(goalLabel)) {
        return currentGoals.filter((goal) => goal !== goalLabel)
      }

      return [...currentGoals, goalLabel]
    })
  }

  function handlePlatformToggle(platformName: string) {
    setConnectedPlatforms((currentPlatforms) => {
      if (currentPlatforms.includes(platformName)) {
        return currentPlatforms.filter((platform) => platform !== platformName)
      }

      return [...currentPlatforms, platformName]
    })
  }

  async function continueAuthenticatedFlow(specialistId = selectedSpecialist) {
    suppressAutoRestoreRef.current = false
    const snapshot = await readWorkspaceSnapshot()

    if (snapshot) {
      restoreWorkspace(snapshot)
      return
    }

    setSelectedSpecialist(specialistId)
    moveToStep('website')
  }

  async function handleSpecialistSelect(specialistId: string) {
    suppressAutoRestoreRef.current = false
    setSelectedSpecialist(specialistId)

    if (!currentUser) {
      moveToStep('website')
      return
    }

    const snapshot = await readWorkspaceSnapshot()

    if (snapshot) {
      restoreWorkspace(snapshot)
      return
    }

    moveToStep('website')
  }

  async function handleGoogleContinue() {
    if (!auth || !googleProvider) {
      setAuthError(firebaseInitError || 'Google ile giriş şu an kullanılamıyor.')
      return
    }

    setAuthPending(true)
    setAuthError(null)

    try {
      await signInWithPopup(auth, googleProvider)
      await claimGuestWorkspaceIfNeeded()
      setAuthDialogOpen(false)
      await continueAuthenticatedFlow()
    } catch (error) {
      setAuthError(readFirebaseError(error))
    } finally {
      setAuthPending(false)
    }
  }

  async function handleEmailAuth() {
    if (!auth) {
      setAuthError(firebaseInitError || 'E-posta ile giriş şu an kullanılamıyor.')
      return
    }

    setAuthPending(true)
    setAuthError(null)

    try {
      const normalizedEmail = email.trim()
      const normalizedPassword = password.trim()

      if (!normalizedEmail || !normalizedPassword) {
        setAuthError('E-posta ve şifre alanlarını doldurun.')
        return
      }

      const signInMethods = await fetchSignInMethodsForEmail(auth, normalizedEmail)

      if (signInMethods.includes('google.com') && !signInMethods.includes('password')) {
        setAuthError('Bu e-posta Google hesabıyla kullanılıyor. Google ile devam edin.')
        return
      }

      if (signInMethods.includes('password')) {
        await signInWithEmailAndPassword(auth, normalizedEmail, normalizedPassword)
      } else {
        const credentials = await createUserWithEmailAndPassword(
          auth,
          normalizedEmail,
          normalizedPassword,
        )

        if (name.trim()) {
          await updateProfile(credentials.user, {
            displayName: name.trim(),
          })
        }
      }

      suppressAutoRestoreRef.current = false
      await claimGuestWorkspaceIfNeeded()
      setAuthDialogOpen(false)
      await continueAuthenticatedFlow()
    } catch (error) {
      setAuthError(readFirebaseError(error))
    } finally {
      setAuthPending(false)
    }
  }

  function handleWebsiteContinue() {
    if (!website.trim()) {
      return
    }

    setWebsite(normalizeWebsite(website))
    void enterWorkspace()
  }

  async function enterWorkspace() {
    if (!website.trim()) {
      return
    }

    const normalizedSource = normalizeWebsite(website)
    setWebsite(normalizedSource)

    const runId = analysisRunRef.current + 1
    analysisRunRef.current = runId

    setActiveFileId(null)
    setTrialActivated(false)
    setAnalysisPhase(1)
    setAnalysisPending(true)
    setAnalysisError(null)
    setChatError(null)
    setChatDraft('')
    setChatRemainingMessages(CHAT_MESSAGE_LIMIT)
    setPendingChatMessage(null)
    setAnalysisResult(null)
    moveToStep('workspace')

    try {
      const result = currentUser
        ? await analyzeWebsite({
            website: normalizedSource,
            goals: selectedGoals,
            connectedPlatforms,
          })
        : await analyzeGuestWebsite(
            {
              website: normalizedSource,
              goals: selectedGoals,
              connectedPlatforms,
            },
            await ensureGuestSessionId(),
          )
      const normalizedResult = normalizeAnalyzeResponse(result)

      if (analysisRunRef.current !== runId) {
        return
      }

      if (!normalizedResult) {
        throw new Error('Analiz çıktısı beklenen formatta gelmedi.')
      }

      if (currentUser) {
        const snapshot = normalizeWorkspaceSnapshot({
          website: normalizedSource,
          selectedGoals,
          connectedPlatforms,
          analysisResult: normalizedResult,
          trialActivated: false,
          selectedSpecialist,
        })
        if (snapshot) {
          lastPersistedSnapshotRef.current = buildSnapshotSignature(snapshot)
          await writeWorkspaceSnapshot(snapshot)
        }
      }

      setAnalysisResult(normalizedResult)
      setAnalysisPhase(4)
    } catch (error) {
      if (analysisRunRef.current !== runId) {
        return
      }

      setAnalysisPhase(4)
      setAnalysisError(
        error instanceof Error ? error.message : 'Website analizi başarısız oldu.',
      )
    } finally {
      if (analysisRunRef.current === runId) {
        setAnalysisPending(false)
      }
    }
  }

  async function handleSignOut() {
    if (!auth) {
      return
    }

    suppressAutoRestoreRef.current = true
    hasAutoRestoredWorkspaceRef.current = true
    lastPersistedSnapshotRef.current = null
    invalidateAnalysisRun()
    setSelectedSpecialist('aylin')
    setWebsite('')
    setConnectedPlatforms([])
    setSelectedGoals(DEFAULT_GOALS)
    setTrialActivated(false)
    setAnalysisPhase(0)
    setAnalysisError(null)
    setChatError(null)
    setChatDraft('')
    setChatRemainingMessages(CHAT_MESSAGE_LIMIT)
    setPendingChatMessage(null)
    setStep('specialist')
    setAnalysisResult(null)
    setActiveFileId(null)
    await signOut(auth)
  }

  function resetDemo() {
    suppressAutoRestoreRef.current = true
    lastPersistedSnapshotRef.current = null
    invalidateAnalysisRun()
    setSelectedSpecialist('aylin')
    setAuthMode('signup')
    setName('')
    setEmail('')
    setPassword('')
    setWebsite('')
    setConnectedPlatforms([])
    setSelectedGoals(DEFAULT_GOALS)
    setActiveFileId(null)
    setTrialActivated(false)
    setAnalysisPhase(0)
    setAnalysisError(null)
    setChatError(null)
    setChatDraft('')
    setChatRemainingMessages(CHAT_MESSAGE_LIMIT)
    setPendingChatMessage(null)
    setAnalysisResult(null)
    setStep('specialist')
  }

  async function handleChatSubmit() {
    const trimmedMessage = chatDraft.trim()
    if (!trimmedMessage || !analysisResult || analysisPending || chatPending) {
      return
    }

    if (chatRemainingMessages <= 0) {
      setChatError(`Bu oturum için maksimum ${CHAT_MESSAGE_LIMIT} mesaj hakkı doldu.`)
      return
    }

    setChatPending(true)
    setChatError(null)
    setPendingChatMessage(trimmedMessage)
    setChatDraft('')

    try {
      const response = normalizeChatMessageResponse(
        currentUser
          ? await sendChatMessage(trimmedMessage)
          : await sendGuestChatMessage(trimmedMessage, await ensureGuestSessionId()),
      )
      if (!response) {
        throw new Error('Sohbet yanıtı beklenen formatta gelmedi.')
      }

      setAnalysisResult((current) => {
        if (!current) {
          return current
        }

        return {
          ...current,
          chatThread: response.chatThread,
        }
      })
      setChatRemainingMessages(response.remainingUserMessages)
      setPendingChatMessage(null)
    } catch (error) {
      setChatError(
        error instanceof Error ? error.message : 'Sohbet mesajı gönderilemedi.',
      )
      setPendingChatMessage(null)
      setChatDraft(trimmedMessage)
    } finally {
      setChatPending(false)
    }
  }

  return (
    <div className={`app-shell ${isWorkspace ? 'workspace-mode' : ''} ${step === 'specialist' ? 'landing-mode' : ''}`}>
      {!isWorkspace && step !== 'specialist' ? <div className="ambient ambient-one"></div> : null}
      {!isWorkspace && step !== 'specialist' ? <div className="ambient ambient-two"></div> : null}
      {!isWorkspace && step !== 'specialist' ? <div className="ambient ambient-grid"></div> : null}

      {!isWorkspace && step !== 'specialist' ? (
        <header className="app-header">
          <div className="brand-lockup">
            <div>
              <p className="brand-name">Olric.</p>
              <p className="brand-subtitle">Bağlantıyı girin, ilk analizi dakikalar içinde açalım.</p>
            </div>
          </div>

          <p className="header-caption">
            Website ya da herkese açık sosyal medya profilini girin. Olric misafir olarak içeri alır
            ve çalışma alanını anında oluşturur.
          </p>

          <div className="header-actions">
            {currentUser ? (
              <div className="user-chip">
                <span>{currentUser.displayName || currentUser.email || 'Oturum açık'}</span>
                <button
                  type="button"
                  className="ghost-button compact-button"
                  onClick={handleSignOut}
                >
                  Çıkış yap
                </button>
              </div>
            ) : (
              <button
                type="button"
                className="ghost-button compact-button"
                onClick={() => openAuthDialog('signin')}
              >
                Giriş yap
              </button>
            )}

            <button type="button" className="ghost-button" onClick={handleBack}>
              Geri
            </button>
          </div>
        </header>
      ) : null}

      {step === 'specialist' ? (
        <RevolutLanding
          onStart={() => {
            void handleSpecialistSelect('aylin')
          }}
          onLogin={() => {
            if (currentUser) {
              void continueAuthenticatedFlow('aylin')
              return
            }

            openAuthDialog('signin')
          }}
        />
      ) : null}

      {step === 'signup' ? (
        <section className="screen split-screen">
          <div className="form-panel">
            <p className="eyebrow">{currentSpecialist.name} ile tanış</p>
            <h1>İlk otonom pazarlama katmanınız hazır.</h1>
            <p className="lede compact">
              Uzun kurulumlarla zaman kaybetmeden markayı öğrenir, stratejiyi kurar ve ilk
              çıktıları hazırlar.
            </p>

            {currentUser ? (
              <div className="auth-summary-card">
                <p className="mini-label">Giriş açık</p>
                <h2>{currentUser.displayName || 'Tekrar hoş geldiniz'}</h2>
                <p>{currentUser.email}</p>
                <button
                  type="button"
                  className="primary-button wide-button"
                  onClick={() => moveToStep('website')}
                >
                  {currentUser.displayName || currentUser.email} olarak devam et
                </button>
              </div>
            ) : (
              <>
                <div className="auth-toggle">
                  <button
                    type="button"
                    className={authMode === 'signup' ? 'secondary-button' : 'ghost-button'}
                    onClick={() => setAuthMode('signup')}
                  >
                    Hesap oluştur
                  </button>
                  <button
                    type="button"
                    className={authMode === 'signin' ? 'secondary-button' : 'ghost-button'}
                    onClick={() => setAuthMode('signin')}
                  >
                    Giriş yap
                  </button>
                </div>

                <button
                  type="button"
                  className="google-button auth-google-button"
                  disabled={authPending}
                  onClick={() => {
                    void handleGoogleContinue()
                  }}
                >
                  <GoogleLogo />
                  <span>{authPending ? 'Google hesabı bağlanıyor...' : 'Google ile devam et'}</span>
                </button>

                <div className="divider-row">
                  <span></span>
                  <p>veya e-posta ile ilerle</p>
                  <span></span>
                </div>

                <form
                  className="auth-form"
                  onSubmit={(event) => {
                    event.preventDefault()
                    void handleEmailAuth()
                  }}
                >
                  {authMode === 'signup' ? (
                    <label>
                      Adınız
                      <input
                        type="text"
                        placeholder="Olric size adınızla hitap etsin"
                        value={name}
                        onChange={(event) => setName(event.target.value)}
                      />
                    </label>
                  ) : null}

                  <label>
                    E-posta
                    <input
                      type="email"
                      placeholder="kurucu@markan.com"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                    />
                  </label>
                  <label>
                    Şifre
                    <input
                      type="password"
                      placeholder={
                        authMode === 'signup' ? 'Güçlü bir şifre oluşturun' : 'Şifrenizi girin'
                      }
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                    />
                  </label>

                  {authError ? <p className="inline-error">{authError}</p> : null}

                  <button
                    type="submit"
                    className="primary-button wide-button"
                    disabled={authPending}
                  >
                    {authPending
                      ? 'İşleniyor...'
                      : authMode === 'signup'
                        ? 'Hesap oluştur'
                        : 'Giriş yap'}
                  </button>
                </form>
              </>
            )}
          </div>

          <div className="visual-panel">
            <div className="tag-cloud">
              {capabilityTags.map((tag) => (
                <span key={tag} className="floating-tag">
                  {tag}
                </span>
              ))}
            </div>

            <div className="visual-card">
              <p className="mini-label">Bu yapının farkı</p>
              <h2>Olric karar sürecini görünür kılar.</h2>
              <p>
                Boş bir yükleme ekranı yerine ne yaptığını anlatır, hafıza dosyalarını oluşturur
                ve sonraki kararları hangi mantıkla verdiğini açık biçimde gösterir.
              </p>
            </div>
          </div>
        </section>
      ) : null}

      {step === 'website' ? (
        <section className="screen centered-screen">
          <div className="focus-card source-entry-card">
            <p className="eyebrow">Olric ile başla</p>
            <h1>Website veya sosyal medya bağlantısını girin.</h1>
            <p className="lede compact">
              Website, herkese açık bir Instagram profili, LinkedIn sayfası ya da tekil bir içerik
              bağlantısı olabilir. Olric kaynağı tarar, hafıza dosyalarını üretir ve sizi doğrudan
              çalışma alanına alır.
            </p>

            <div className="source-search-shell">
              <input
                type="url"
                className="source-search-input"
                placeholder="https://markaniz.com veya https://instagram.com/kullaniciadi"
                value={website}
                onChange={(event) => setWebsite(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && website.trim()) {
                    event.preventDefault()
                    handleWebsiteContinue()
                  }
                }}
              />
              <button
                type="button"
                className="primary-button source-search-button"
                disabled={!website.trim()}
                onClick={handleWebsiteContinue}
              >
                Olric ile başlayın
              </button>
            </div>
          </div>
        </section>
      ) : null}

      {step === 'goals' ? (
        <GoalsStep
          selectedGoals={selectedGoals}
          onToggle={handleGoalToggle}
          onContinue={() => moveToStep('integrations')}
        />
      ) : null}

      {step === 'integrations' ? (
        <IntegrationsStep
          connectedPlatforms={connectedPlatforms}
          onToggle={handlePlatformToggle}
          onContinue={() => {
            void enterWorkspace()
          }}
        />
      ) : null}

      {step === 'workspace' ? (
        <WorkspaceStep
          activeFileId={activeFileId}
          analysis={analysis}
          analysisError={analysisError}
          analysisPending={analysisPending}
          analysisPhase={analysisPhase}
          chatDraft={chatDraft}
          chatError={chatError}
          pendingChatMessage={pendingChatMessage}
          chatPending={chatPending}
          chatRemainingMessages={chatRemainingMessages}
          currentSpecialist={currentSpecialist}
          isGuest={!currentUser}
          chatThread={chatThread}
          memoryFiles={memoryFiles}
          onOpenAuth={() => openAuthDialog('signin')}
          onChatDraftChange={setChatDraft}
          onChatSubmit={() => {
            void handleChatSubmit()
          }}
          qualityReview={qualityReview}
          onActivateTrial={() => setTrialActivated(true)}
          onOpenFile={setActiveFileId}
          onRestart={resetDemo}
          onSignOut={() => {
            void handleSignOut()
          }}
          selectedGoals={selectedGoals}
          strategicSummary={strategicSummary}
          trialActivated={trialActivated}
          userLabel={currentUser?.displayName || currentUser?.email || 'Misafir'}
          website={website}
        />
      ) : null}

      {authDialogOpen ? (
        <AuthDialog
          authAvailable={Boolean(firebaseReady && auth)}
          authError={authError}
          authPending={authPending}
          email={email}
          onClose={closeAuthDialog}
          onEmailChange={setEmail}
          onPasswordChange={setPassword}
          onPrimaryAction={() => {
            void handleGoogleContinue()
          }}
          onSubmit={() => {
            void handleEmailAuth()
          }}
          password={password}
        />
      ) : null}

      {activeFile ? (
        <div
          className="modal-backdrop"
          onClick={() => setActiveFileId(null)}
          role="presentation"
        >
          <div
            className="modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="memory-file-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <p className="file-pill">{activeFile.filename}</p>
                <h2 id="memory-file-title">{activeFile.title}</h2>
              </div>
              <button
                type="button"
                className="ghost-button"
                onClick={() => setActiveFileId(null)}
              >
                Kapat
              </button>
            </div>

            <div className="markdown-viewer">{renderMarkdownContent(activeFile.content)}</div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

type AuthDialogProps = {
  authAvailable: boolean
  authError: string | null
  authPending: boolean
  email: string
  onClose: () => void
  onEmailChange: (value: string) => void
  onPasswordChange: (value: string) => void
  onPrimaryAction: () => void
  onSubmit: () => void
  password: string
}

function GoogleLogo() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="google-mark">
      <path
        fill="#4285F4"
        d="M21.6 12.23c0-.74-.06-1.45-.2-2.13H12v4.04h5.38a4.6 4.6 0 0 1-2 3.02v2.5h3.24c1.9-1.75 2.98-4.33 2.98-7.43Z"
      />
      <path
        fill="#34A853"
        d="M12 22c2.7 0 4.96-.9 6.62-2.43l-3.24-2.5c-.9.6-2.04.96-3.38.96-2.6 0-4.8-1.76-5.58-4.13H3.08v2.58A10 10 0 0 0 12 22Z"
      />
      <path
        fill="#FBBC05"
        d="M6.42 13.9A5.98 5.98 0 0 1 6.1 12c0-.66.12-1.3.32-1.9V7.52H3.08A10 10 0 0 0 2 12c0 1.6.38 3.1 1.08 4.48l3.34-2.58Z"
      />
      <path
        fill="#EA4335"
        d="M12 5.97c1.47 0 2.8.5 3.84 1.5l2.88-2.88C16.95 2.94 14.7 2 12 2 8.08 2 4.7 4.24 3.08 7.52l3.34 2.58C7.2 7.73 9.4 5.97 12 5.97Z"
      />
    </svg>
  )
}

function AuthDialog({
  authAvailable,
  authError,
  authPending,
  email,
  onClose,
  onEmailChange,
  onPasswordChange,
  onPrimaryAction,
  onSubmit,
  password,
}: AuthDialogProps) {
  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div
        className="modal-card auth-dialog-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-dialog-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header auth-dialog-header">
          <div>
            <h2 id="auth-dialog-title">Devam edin</h2>
          </div>
          <button type="button" className="ghost-button compact-button" onClick={onClose}>
            Kapat
          </button>
        </div>

        <div className="auth-dialog-grid">
          <section className="auth-dialog-panel auth-dialog-panel-form">
            <button
              type="button"
              className="google-button auth-google-button"
              disabled={authPending || !authAvailable}
              onClick={onPrimaryAction}
            >
              <GoogleLogo />
              <span>{authPending ? 'Google hesabı bağlanıyor...' : 'Google ile devam et'}</span>
            </button>

            <div className="divider-row auth-divider-row">
              <span></span>
              <p>veya</p>
              <span></span>
            </div>

            <form
              className="auth-form"
              onSubmit={(event) => {
                event.preventDefault()
                onSubmit()
              }}
            >
              <label>
                E-posta
                <input
                  type="email"
                  placeholder="kurucu@markaniz.com"
                  value={email}
                  disabled={!authAvailable}
                  onChange={(event) => onEmailChange(event.target.value)}
                />
              </label>
              <label>
                Şifre
                <input
                  type="password"
                  placeholder="Şifrenizi girin"
                  value={password}
                  disabled={!authAvailable}
                  onChange={(event) => onPasswordChange(event.target.value)}
                />
              </label>

              {authError ? <p className="inline-error">{authError}</p> : null}

              <button
                type="submit"
                className="primary-button wide-button"
                disabled={authPending || !authAvailable}
              >
                {authPending ? 'İşleniyor...' : 'Devam et'}
              </button>
            </form>
          </section>
        </div>
      </div>
    </div>
  )
}

export default App

function readFirebaseError(error: unknown) {
  if (!error || typeof error !== 'object' || !('code' in error)) {
    return 'Giriş işlemi tamamlanamadı.'
  }

  const code = String(error.code)

  if (code.includes('popup-closed')) {
    return 'Google penceresi tamamlanmadan kapatıldı.'
  }

  if (code.includes('invalid-credential')) {
    return 'E-posta veya şifre doğrulanamadı.'
  }

  if (code.includes('email-already-in-use')) {
    return 'Bu e-posta zaten kayıtlı. Aynı bilgilerle devam edin.'
  }

  if (code.includes('weak-password')) {
    return 'Şifre en az 6 karakter olmalı.'
  }

  if (code.includes('too-many-requests')) {
    return 'Çok fazla deneme yapıldı. Kısa süre sonra tekrar deneyin.'
  }

  return 'Giriş işlemi tamamlanamadı.'
}

type GoalsStepProps = {
  selectedGoals: string[]
  onToggle: (goalLabel: string) => void
  onContinue: () => void
}

function GoalsStep({ selectedGoals, onToggle, onContinue }: GoalsStepProps) {
  return (
    <section className="screen centered-screen">
      <div className="focus-card large-card">
        <p className="eyebrow">Olric’in odağını belirleyin</p>
        <h1>Hangi alanlarda destek istiyorsunuz?</h1>
        <p className="lede compact">
          Birini ya da birkaçını seçin. Olric bu sinyalleri analiz kapsamını ve ilk ay planını
          ağırlıklandırmak için kullanacak.
        </p>

        <div className="goal-grid">
          {goalOptions.map((goal) => (
            <button
              key={goal.id}
              type="button"
              className={`goal-card ${selectedGoals.includes(goal.label) ? 'selected' : ''}`}
              onClick={() => onToggle(goal.label)}
            >
              <span className="goal-short">{goal.short}</span>
              <span className="goal-label">{goal.label}</span>
              <span className="goal-blurb">{goal.blurb}</span>
            </button>
          ))}
        </div>

        <button
          type="button"
          className="primary-button wide-button"
          disabled={selectedGoals.length === 0}
          onClick={onContinue}
        >
          Devam et
        </button>
      </div>
    </section>
  )
}

type IntegrationsStepProps = {
  connectedPlatforms: string[]
  onToggle: (platformName: string) => void
  onContinue: () => void
}

function IntegrationsStep({
  connectedPlatforms,
  onToggle,
  onContinue,
}: IntegrationsStepProps) {
  return (
    <section className="screen centered-screen">
      <div className="focus-card large-card">
        <p className="eyebrow">Opsiyonel bağlantılar</p>
        <h1>Platformlarınızı bağlayın</h1>
        <p className="lede compact">
          Bu hesaplar Olric’in daha hızlı ilerlemesini sağlar. İsterseniz şimdilik atlayıp yalnızca
          website verisiyle de başlayabilirsiniz.
        </p>

        <div className="platform-grid">
          {platformOptions.map((platform) => {
            const isConnected = connectedPlatforms.includes(platform.name)

            return (
              <article key={platform.id} className="platform-card">
                <div className="platform-mark">
                  {platform.name
                    .split(' ')
                    .map((part) => part.charAt(0))
                    .join('')
                    .slice(0, 2)
                    .toUpperCase()}
                </div>
                <div className="platform-copy">
                  <h2>{platform.name}</h2>
                  <p>{platform.blurb}</p>
                </div>
                <button
                  type="button"
                  className={isConnected ? 'secondary-button' : 'ghost-button'}
                  onClick={() => onToggle(platform.name)}
                >
                  {isConnected ? 'Bağlandı' : 'Bağla'}
                </button>
              </article>
            )
          })}
        </div>

        <button type="button" className="primary-button wide-button" onClick={onContinue}>
          {connectedPlatforms.length > 0 ? 'Canlı analize geç' : 'Şimdilik atla'}
        </button>
      </div>
    </section>
  )
}

const MARKDOWN_TABLE_SEPARATOR_PATTERN =
  /^\s*\|?(?:\s*:?-{3,}:?\s*\|)+(?:\s*:?-{3,}:?\s*)\|?\s*$/

function renderInlineMarkdown(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean)

  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={`${part}-${index}`}>{part.slice(2, -2)}</strong>
    }

    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={`${part}-${index}`} className="inline-code">
          {part.slice(1, -1)}
        </code>
      )
    }

    return <span key={`${part}-${index}`}>{part}</span>
  })
}

function splitMarkdownTableRow(line: string) {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim())
}

function renderMarkdownContent(content: string) {
  const lines = content.replace(/\r/g, '').split('\n')
  const blocks: ReactNode[] = []
  let index = 0

  while (index < lines.length) {
    const rawLine = lines[index] ?? ''
    const line = rawLine.trim()

    if (!line) {
      index += 1
      continue
    }

    const headingMatch = line.match(/^(#{1,3})\s+(.*)$/)
    if (headingMatch) {
      const level = headingMatch[1].length
      const headingText = headingMatch[2].trim()

      if (level === 1) {
        blocks.push(
          <h1 key={`md-heading-${index}`} className="markdown-h1">
            {renderInlineMarkdown(headingText)}
          </h1>,
        )
      } else if (level === 2) {
        blocks.push(
          <h2 key={`md-heading-${index}`} className="markdown-h2">
            {renderInlineMarkdown(headingText)}
          </h2>,
        )
      } else {
        blocks.push(
          <h3 key={`md-heading-${index}`} className="markdown-h3">
            {renderInlineMarkdown(headingText)}
          </h3>,
        )
      }

      index += 1
      continue
    }

    if (
      line.startsWith('|') &&
      index + 1 < lines.length &&
      MARKDOWN_TABLE_SEPARATOR_PATTERN.test((lines[index + 1] ?? '').trim())
    ) {
      const headerCells = splitMarkdownTableRow(line)
      const rows: string[][] = []
      index += 2

      while (index < lines.length) {
        const tableLine = (lines[index] ?? '').trim()
        if (!tableLine.startsWith('|')) {
          break
        }
        rows.push(splitMarkdownTableRow(tableLine))
        index += 1
      }

      blocks.push(
        <div key={`md-table-${index}`} className="markdown-table-wrap">
          <table className="markdown-table">
            <thead>
              <tr>
                {headerCells.map((cell, cellIndex) => (
                  <th key={`md-table-head-${cellIndex}`}>{renderInlineMarkdown(cell)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={`md-table-row-${rowIndex}`}>
                  {row.map((cell, cellIndex) => (
                    <td key={`md-table-cell-${rowIndex}-${cellIndex}`}>
                      {renderInlineMarkdown(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      )
      continue
    }

    if (/^[-*]\s+/.test(line)) {
      const items: string[] = []
      while (index < lines.length) {
        const listLine = (lines[index] ?? '').trim()
        if (!/^[-*]\s+/.test(listLine)) {
          break
        }
        items.push(listLine.replace(/^[-*]\s+/, '').trim())
        index += 1
      }

      blocks.push(
        <ul key={`md-list-${index}`} className="markdown-list">
          {items.map((item, itemIndex) => (
            <li key={`md-list-item-${itemIndex}`}>{renderInlineMarkdown(item)}</li>
          ))}
        </ul>,
      )
      continue
    }

    if (/^\d+\.\s+/.test(line)) {
      const items: string[] = []
      while (index < lines.length) {
        const listLine = (lines[index] ?? '').trim()
        if (!/^\d+\.\s+/.test(listLine)) {
          break
        }
        items.push(listLine.replace(/^\d+\.\s+/, '').trim())
        index += 1
      }

      blocks.push(
        <ol key={`md-ordered-list-${index}`} className="markdown-ordered-list">
          {items.map((item, itemIndex) => (
            <li key={`md-ordered-item-${itemIndex}`}>{renderInlineMarkdown(item)}</li>
          ))}
        </ol>,
      )
      continue
    }

    const paragraphLines: string[] = [line]
    index += 1

    while (index < lines.length) {
      const nextLine = (lines[index] ?? '').trim()
      if (
        !nextLine ||
        /^(#{1,3})\s+/.test(nextLine) ||
        /^[-*]\s+/.test(nextLine) ||
        /^\d+\.\s+/.test(nextLine) ||
        (
          nextLine.startsWith('|') &&
          index + 1 < lines.length &&
          MARKDOWN_TABLE_SEPARATOR_PATTERN.test((lines[index + 1] ?? '').trim())
        )
      ) {
        break
      }
      paragraphLines.push(nextLine)
      index += 1
    }

    blocks.push(
      <p key={`md-paragraph-${index}`} className="markdown-paragraph">
        {renderInlineMarkdown(paragraphLines.join(' '))}
      </p>,
    )
  }

  return <div className="markdown-document">{blocks}</div>
}

type WorkspaceStepProps = {
  activeFileId: string | null
  analysis: Analysis
  analysisError: string | null
  analysisPending: boolean
  analysisPhase: number
  chatDraft: string
  chatError: string | null
  pendingChatMessage: string | null
  chatPending: boolean
  chatRemainingMessages: number
  chatThread: ChatThread | null
  currentSpecialist: (typeof specialists)[number]
  isGuest: boolean
  memoryFiles: MemoryFile[]
  onOpenAuth: () => void
  onChatDraftChange: (value: string) => void
  onChatSubmit: () => void
  qualityReview: QualityReview | null
  onActivateTrial: () => void
  onOpenFile: (fileId: string) => void
  onRestart: () => void
  onSignOut: () => void
  selectedGoals: string[]
  strategicSummary: StrategicSummary | null
  trialActivated: boolean
  userLabel: string
  website: string
}

function WorkspaceStep({
  activeFileId,
  analysis,
  analysisError,
  analysisPending,
  analysisPhase,
  chatDraft,
  chatError,
  pendingChatMessage,
  chatPending,
  chatRemainingMessages,
  chatThread,
  currentSpecialist,
  isGuest,
  memoryFiles,
  onOpenAuth,
  onChatDraftChange,
  onChatSubmit,
  qualityReview,
  onActivateTrial,
  onOpenFile,
  onRestart,
  onSignOut,
  selectedGoals,
  strategicSummary,
  trialActivated,
  userLabel,
  website,
}: WorkspaceStepProps) {
  const dateLabel = new Intl.DateTimeFormat('tr-TR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  }).format(new Date())
  const strategyFile =
    memoryFiles.find((file) => file.id === 'strategy') || memoryFiles[0] || null
  const brandMark = analysis.companyName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0))
    .join('')
    .toUpperCase()
  const workspaceTitle = trialActivated
    ? 'Olric aktif'
    : analysisPending
      ? 'Canlı analiz'
      : analysisError
        ? 'Analiz durduruldu'
        : 'Analiz tamamlandı'
  const specialistAvatar = currentSpecialist.avatar
  const visibleFilePreviews = memoryFiles.slice(0, 4)
  const threadMessages = chatThread?.messages ?? []
  const isChatLocked = chatRemainingMessages <= 0
  const historyTitle = chatThread?.title || `${analysis.companyName} için ilk analiz`
  const [dismissedLogoUrl, setDismissedLogoUrl] = useState<string | null>(null)
  const [expandedInlineFileId, setExpandedInlineFileId] = useState<string | null | undefined>(undefined)
  const [copiedFileId, setCopiedFileId] = useState<string | null>(null)
  const [showAllKnowledgeFiles, setShowAllKnowledgeFiles] = useState(false)
  const chatThreadRef = useRef<HTMLDivElement | null>(null)
  const preferredWorkspaceLogoUrl =
    analysis.brandAssets?.brandLogo ||
    analysis.brandAssets?.favicon ||
    analysis.brandAssets?.touchIcon ||
    analysis.logoUrl ||
    null
  const workspaceLogoUrl =
    preferredWorkspaceLogoUrl && dismissedLogoUrl !== preferredWorkspaceLogoUrl
      ? preferredWorkspaceLogoUrl
      : null
  const livePrimaryAttachments = buildLiveMemoryAttachments(memoryFiles, 0, 2, [
    {
      id: 'business-profile',
      filename: 'business-profile.md',
      title: `${analysis.companyName} — İşletme Profili`,
      blurb: 'Şirketin teklif yapısı, hedef kitlesi ve iş modeli netleştiriliyor.',
    },
    {
      id: 'brand-guidelines',
      filename: 'brand-guidelines.md',
      title: `${analysis.companyName} — Marka Kılavuzu`,
      blurb: 'Görsel kimlik, ton ve ana mesaj sütunları çalışma alanına kaydediliyor.',
    },
  ])
  const liveSecondaryAttachments = buildLiveMemoryAttachments(memoryFiles, 2, 4, [
    {
      id: 'market-research',
      filename: 'market-research.md',
      title: `${analysis.companyName} — Pazar Araştırması`,
      blurb: 'Kategori, rekabet ve büyüme fırsatları ikinci dalga dosyalara ekleniyor.',
    },
    {
      id: 'strategy',
      filename: 'strategy.md',
      title: `${analysis.companyName} — Pazarlama Stratejisi`,
      blurb: 'İlk 30 günün öncelikleri ve büyüme kaldıraçları strateji dosyasına yazılıyor.',
    },
  ])
  const resolvedExpandedInlineFileId =
    expandedInlineFileId === null
      ? null
      : expandedInlineFileId && memoryFiles.some((file) => file.id === expandedInlineFileId)
        ? expandedInlineFileId
        : memoryFiles[0]?.id ?? null
  const knowledgeFiles = showAllKnowledgeFiles ? memoryFiles : memoryFiles.slice(0, 2)
  const firstWorkflowNotes = [
    {
      title: 'Kaynağı inceliyorum',
      detail: 'Sayfaları, profil yapısını ve teklif dilini tek bir akışta toparlıyorum.',
    },
    {
      title: 'Marka sinyallerini çıkarıyorum',
      detail: 'Dil, konumlandırma ve güven katmanlarını ilk çerçeveye yerleştiriyorum.',
    },
    {
      title: 'İlk dosyaları hazırlıyorum',
      detail: 'İşletme profili ve marka kılavuzu için temel iskeleti kuruyorum.',
    },
  ]
  const firstDropNotes = [
    {
      title: 'Teklif yapısını netliyorum',
      detail: 'Hizmetleri, ürünleri ve hedef kitleyi ortak bir profilde birleştiriyorum.',
    },
    {
      title: 'Marka dilini sabitliyorum',
      detail: 'Renk, ton ve CTA yapısını marka kılavuzuna işliyorum.',
    },
  ]
  const secondDropNotes = [
    {
      title: 'Pazarı tarıyorum',
      detail: 'Kategori fırsatlarını, içerik boşluklarını ve rekabet sinyallerini ayıklıyorum.',
    },
    {
      title: 'İlk yol haritasını yazıyorum',
      detail: 'İlk 30 gün için uygulanabilir büyüme adımlarını strateji dosyasına aktarıyorum.',
    },
  ]
  const requestedTopics =
    selectedGoals.length > 0
      ? selectedGoals.join(', ')
      : 'Sosyal Medya, E-posta Pazarlaması, Ücretli Reklamlar, SEO, İçerik Yazımı'
  const shouldShowTrialCta =
    !analysisPending &&
    !analysisError &&
    (threadMessages.length > 0 || analysisPhase >= 7)
  const formatMessageTime = (value?: string | null) => {
    const date = value ? new Date(value) : new Date()
    if (Number.isNaN(date.getTime())) {
      return ''
    }

    return new Intl.DateTimeFormat('tr-TR', {
      hour: '2-digit',
      minute: '2-digit',
    }).format(date)
  }

  useEffect(() => {
    const element = chatThreadRef.current
    if (!element) {
      return
    }

    const handle = window.requestAnimationFrame(() => {
      element.scrollTo({
        top: element.scrollHeight,
        behavior: 'smooth',
      })
    })

    return () => window.cancelAnimationFrame(handle)
  }, [
    analysisPending,
    analysisPhase,
    chatPending,
    pendingChatMessage,
    chatError,
    analysisError,
    threadMessages.length,
  ])

  function renderMessageMeta(author: string, timestamp?: string | null) {
    return (
      <div className="message-meta">
        <p className="message-author">{author}</p>
        <span className="message-time">{formatMessageTime(timestamp)}</span>
      </div>
    )
  }

  function copyFileContent(file: MemoryFile) {
    if (typeof navigator === 'undefined' || !navigator.clipboard?.writeText) {
      return
    }

    void navigator.clipboard.writeText(file.content).then(() => {
      setCopiedFileId(file.id)
      window.setTimeout(() => {
        setCopiedFileId((current) => (current === file.id ? null : current))
      }, 1800)
    })
  }

  function toMemoryAttachment(file: MemoryFile): ChatAttachment {
    return {
      type: 'memory_document',
      id: file.id,
      fileId: file.id,
      filename: file.filename,
      title: file.title,
      blurb: file.blurb,
      version: file.version ?? 1,
      isCurrent: file.isCurrent ?? true,
    }
  }

  function buildLiveMemoryAttachments(
    files: MemoryFile[],
    startIndex: number,
    endIndex: number,
    placeholders: Array<{
      id: string
      filename: string
      title: string
      blurb: string
    }>,
  ): ChatAttachment[] {
    const selectedFiles = files.slice(startIndex, endIndex)

    if (selectedFiles.length > 0) {
      return selectedFiles.map((file) => toMemoryAttachment(file))
    }

    return placeholders.map((placeholder) => ({
      type: 'memory_document',
      id: placeholder.id,
      fileId: placeholder.id,
      filename: placeholder.filename,
      title: placeholder.title,
      blurb: placeholder.blurb,
      version: null,
      isCurrent: true,
    }))
  }

  function renderAssistantMessage(content: ReactNode, className = '', timestamp?: string | null) {
    return (
      <div className="assistant-chat-row">
        <img
          src={specialistAvatar}
          alt={`${currentSpecialist.name} avatarı`}
          className="assistant-chat-avatar"
        />
        <article className={`chat-message assistant-message ${className}`.trim()}>
          {renderMessageMeta(currentSpecialist.name, timestamp)}
          {content}
        </article>
      </div>
    )
  }

  function renderUserMessage() {
    return (
      <div className="user-chat-row">
        <article className="chat-message user-message">
          {renderMessageMeta(userLabel)}
          <p>
            Kaynağımız "{normalizeWebsite(website)}". {requestedTopics} konularında bize yardımcı
            olabilir misiniz?
          </p>
        </article>
      </div>
    )
  }

  function renderWorkflowNotes(
    notes: Array<{ title: string; detail: string }>,
    activeCount = notes.length,
    isComplete = false,
  ) {
    const visibleNotes = notes.slice(0, Math.max(1, Math.min(activeCount, notes.length)))

    return (
      <div className="workflow-note-list">
        {visibleNotes.map((note, index) => {
          const isActive = !isComplete && index === visibleNotes.length - 1

          return (
            <div
              key={`${note.title}-${index}`}
              className={`workflow-note-item ${isComplete || !isActive ? 'done' : 'active'}`}
            >
              <span className="workflow-note-dot" aria-hidden="true"></span>
              <div className="workflow-note-copy">
                <strong>{note.title}</strong>
                <p>{note.detail}</p>
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  function renderTextBlocks(content: string) {
    return content
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line, index) => <p key={`${line}-${index}`}>{line}</p>)
  }

  function findMemoryFileByAttachment(attachment: ChatAttachment) {
    return (
      memoryFiles.find((file) => file.id === attachment.fileId) ||
      memoryFiles.find((file) => file.id === attachment.id) ||
      memoryFiles.find((file) => file.filename === attachment.filename) ||
      null
    )
  }

  type InlineMemoryCard = {
    id: string
    filename: string
    title: string
    blurb: string
    content: string
    version: number | null
    isCurrent: boolean
    isPlaceholder: boolean
  }

  function renderMemoryCards(attachments: ChatAttachment[]) {
    const rawCards = attachments
      .map((attachment) => {
        const file = findMemoryFileByAttachment(attachment)

        if (file) {
          return {
            id: file.id,
            filename: file.filename,
            title: file.title,
            blurb: file.blurb,
            content: file.content,
            version: file.version ?? 1,
            isCurrent: file.isCurrent ?? true,
            isPlaceholder: false,
          }
        }

        if (!attachment.id && !attachment.fileId && !attachment.filename) {
          return null
        }

        return {
          id: attachment.fileId || attachment.id || attachment.filename,
          filename: attachment.filename || 'memory-file.md',
          title: attachment.title || attachment.filename || 'Hafıza dosyası',
          blurb: attachment.blurb || attachment.title || 'Dosya hazırlanıyor.',
          content: '',
          version: attachment.version ?? null,
          isCurrent: attachment.isCurrent ?? true,
          isPlaceholder: true,
        }
      })

    const cards: InlineMemoryCard[] = rawCards
      .filter((card): card is InlineMemoryCard => card !== null)

    const fallbackCards: InlineMemoryCard[] = visibleFilePreviews.map((file) => ({
      id: file.id,
      filename: file.filename,
      title: file.title,
      blurb: file.blurb,
      content: file.content,
      version: file.version ?? 1,
      isCurrent: file.isCurrent ?? true,
      isPlaceholder: false,
    }))

    const dedupedCards: InlineMemoryCard[] = (cards.length > 0 ? cards : fallbackCards).filter(
      (file, index, allFiles) => allFiles.findIndex((candidate) => candidate.id === file.id) === index,
    )

    return (
      <div className="chat-file-stack">
        {dedupedCards.map((file) => {
          const isExpanded = !file.isPlaceholder && resolvedExpandedInlineFileId === file.id

          return (
            <article
              key={file.id}
              className={`report-card ${strategyFile?.id === file.id && !file.isPlaceholder ? 'primary-file-card' : ''} ${isExpanded ? 'report-card-expanded' : ''} ${file.isPlaceholder ? 'report-card-loading' : ''}`}
            >
              <div className="report-card-header">
                <div className="report-card-title">
                  <span className="memory-drop-icon">MD</span>
                  <strong>{file.filename}</strong>
                  <span className="report-card-kind">Dosya</span>
                </div>
                <span className={`report-card-status ${file.isPlaceholder ? 'pending' : ''}`}>
                  {file.isPlaceholder ? 'Sırada' : file.version ? `v${file.version}` : 'Kaydedildi'}
                </span>
              </div>
              {isExpanded ? (
                <div className="report-document-shell">{renderMarkdownContent(file.content)}</div>
              ) : (
                <div className="report-card-collapsed">
                  <p>{file.blurb || file.title}</p>
                </div>
              )}
              <div className="report-card-actions">
                {file.isPlaceholder ? (
                  <span className="report-card-note">İçerik tamamlanınca belgeyi açabileceksin.</span>
                ) : (
                  <>
                    <button
                      type="button"
                      className="ghost-button compact-button"
                      onClick={() => setExpandedInlineFileId(isExpanded ? null : file.id)}
                    >
                      {isExpanded ? 'Daralt' : 'Genişlet'}
                    </button>
                    <button
                      type="button"
                      className="ghost-button compact-button"
                      onClick={() => onOpenFile(file.id)}
                    >
                      Tam ekran
                    </button>
                    <button
                      type="button"
                      className={`ghost-button compact-button ${copiedFileId === file.id ? 'copy-success' : ''}`}
                      onClick={() =>
                        copyFileContent({
                          id: file.id,
                          filename: file.filename,
                          title: file.title,
                          blurb: file.blurb,
                          content: file.content,
                          version: file.version,
                          isCurrent: file.isCurrent,
                        })
                      }
                    >
                      {copiedFileId === file.id ? '✓ Kopyalandı' : 'Kopyala'}
                    </button>
                  </>
                )}
              </div>
            </article>
          )
        })}
      </div>
    )
  }

  function renderTrialCta() {
    return (
      <div className="cta-panel">
        <div>
          <p className="mini-label">Hazır olduğunda</p>
          <h2>Olric’i etkinleştir</h2>
          <p>
            3 günlük ücretsiz deneme. Hafıza dosyaları, strateji ve operasyon ritmi
            sende kalsın.
          </p>
        </div>

        <button type="button" className="primary-button" onClick={onActivateTrial}>
          {trialActivated ? 'Deneme aktif' : 'Olric’i etkinleştir'}
        </button>
      </div>
    )
  }

  function renderFinalSummary(content: string, timestamp?: string | null) {
    return (
      <div>
        {renderAssistantMessage(renderTextBlocks(content), 'final-message narrative-message', timestamp)}
      </div>
    )
  }

  function renderPendingUserMessage(content: string) {
    return (
      <div className="user-chat-row">
        <article className="chat-message user-message pending-user-message">
          {renderMessageMeta(userLabel)}
          {renderTextBlocks(content)}
        </article>
      </div>
    )
  }

  function renderTypingIndicator() {
    return renderAssistantMessage(
      <div className="typing-indicator">
        <div className="typing-indicator-copy">
          <strong>Olric yazıyor</strong>
          <p>Mesajını mevcut analiz ve hafıza dosyalarıyla birlikte yorumluyorum.</p>
        </div>
        <div className="typing-dots" aria-label="Yazıyor">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>,
      'typing-message',
    )
  }

  function renderPersistedMessage(message: ChatMessage) {
    if (message.senderType === 'user') {
      return (
        <div key={message.id} className="user-chat-row">
          <article className="chat-message user-message">
            {renderMessageMeta(userLabel, message.createdAt)}
            {renderTextBlocks(message.content)}
          </article>
        </div>
      )
    }

    if (message.messageType === 'process') {
      return <div key={message.id}>{renderWorkflowNotes(firstWorkflowNotes, firstWorkflowNotes.length, true)}</div>
    }

    if (message.messageType === 'memory_files') {
      const isSecondDrop = message.attachments.some(
        (attachment) =>
          attachment.fileId === 'market-research' ||
          attachment.fileId === 'strategy' ||
          attachment.filename.includes('market-research') ||
          attachment.filename.includes('strategy'),
      )

      return (
        <div key={message.id}>
          {renderAssistantMessage(renderTextBlocks(message.content), '', message.createdAt)}
          {renderWorkflowNotes(isSecondDrop ? secondDropNotes : firstDropNotes, undefined, true)}
          {renderMemoryCards(message.attachments)}
        </div>
      )
    }

    if (message.messageType === 'analysis_summary') {
      return <div key={message.id}>{renderFinalSummary(message.content, message.createdAt)}</div>
    }

    return (
      <div key={message.id}>
        {renderAssistantMessage(renderTextBlocks(message.content), '', message.createdAt)}
      </div>
    )
  }

  function renderLiveThread() {
    const finalSummaryLines = [
      'Dosyaları kaydettim.',
      analysis.opportunity
        ? `Öne çıkan büyüme fırsatı: ${analysis.opportunity}`
        : strategicSummary?.primaryGrowthLever
          ? `Öne çıkan büyüme fırsatı: ${strategicSummary.primaryGrowthLever}`
          : '',
      qualityReview?.score
        ? `Analiz kapsam puanı şu anda ${qualityReview.score}/100.`
        : '',
    ].filter(Boolean)

    return (
      <>
        {renderAssistantMessage(
          <p>
            Kaynağı inceleyip ilk pazarlama temelini oluşturmaya başlıyorum.
          </p>,
        )}

        {analysisPhase >= 1 ? (
          renderWorkflowNotes(firstWorkflowNotes, Math.min(analysisPhase, firstWorkflowNotes.length))
        ) : null}

        {analysisPhase >= 2 ? (
          renderAssistantMessage(
            <p>
              İlk görünüm güçlü. {analysis.companyName},{' '}
              {strategicSummary?.positioning || analysis.offer} etrafında
              konumlanıyor gibi görünüyor. En olası hedef kitle{' '}
              {strategicSummary?.bestFitAudience || analysis.audience} ve ayrışan
              çizgi {strategicSummary?.differentiation || analysis.tone}.
            </p>,
          )
        ) : null}

        {analysisPhase >= 3 && !analysisError ? (
          <div>
            {renderAssistantMessage(
              <p>Önce işletme profili ve marka kılavuzunu oluşturmaya başlıyorum.</p>,
            )}
            {renderWorkflowNotes(firstDropNotes, Math.min(Math.max(analysisPhase - 2, 1), firstDropNotes.length))}
            {renderMemoryCards(livePrimaryAttachments)}
          </div>
        ) : null}

        {analysisPhase >= 5 && !analysisError ? (
          renderAssistantMessage(
            <p>
              Şimdi biraz daha derine iniyorum. En güçlü kaldıraç{' '}
              {strategicSummary?.primaryGrowthLever || analysis.opportunity} çizgisinde
              görünüyor. İçerik açısından ise{' '}
              {strategicSummary?.contentAngle || 'daha güçlü bir konu kümelenmesi'}
              öne çıkıyor.
            </p>,
          )
        ) : null}

        {analysisPhase >= 6 && !analysisError ? (
          <div>
            {renderAssistantMessage(
              <p>Şimdi pazar araştırması ve strateji dosyalarını netleştiriyorum.</p>,
            )}
            {renderWorkflowNotes(secondDropNotes, Math.min(Math.max(analysisPhase - 5, 1), secondDropNotes.length))}
            {renderMemoryCards(liveSecondaryAttachments)}
          </div>
        ) : null}

        {analysisPhase >= 7 && !analysisError
          ? renderFinalSummary(finalSummaryLines.join('\n'))
          : null}

        {analysisError
          ? renderAssistantMessage(<p>{analysisError}</p>, 'error-message')
          : null}
      </>
    )
  }

  return (
    <section className="screen workspace-screen">
      <aside className="workspace-sidebar">
        <div className="workspace-brand">
          <div className="workspace-logo">
            {workspaceLogoUrl ? (
              <img
                src={workspaceLogoUrl}
                alt={`${analysis.companyName} logosu`}
                className="workspace-logo-image"
                onError={() => setDismissedLogoUrl(preferredWorkspaceLogoUrl)}
              />
            ) : (
              brandMark || 'AI'
            )}
          </div>
          <div className="workspace-brand-copy">
            <h2>{analysis.companyName}</h2>
            <p className="workspace-subtle">Olric çalışma alanı</p>
          </div>
          <button type="button" className="workspace-brand-toggle" aria-label="Menüyü daralt">
            ‹
          </button>
        </div>

        <div className="sidebar-group">
          <p className="sidebar-heading">Kanallar</p>
          <nav className="nav-stack" aria-label="Workspace sections">
            <button type="button" className="nav-item active">
              # main
            </button>
            <button type="button" className="nav-item">
              # performans
            </button>
            <button type="button" className="nav-item">
              # takvim
            </button>
          </nav>
        </div>

        <div className="sidebar-group">
          <div className="sidebar-section-row">
            <p className="sidebar-heading">Direkt Mesajlar</p>
            <button type="button" className="sidebar-pill-button">
              + Yeni
            </button>
          </div>
          <button type="button" className="dm-card">
            <img
              src={specialistAvatar}
              alt={`${currentSpecialist.name} avatarı`}
              className="dm-avatar-image"
            />
            <span>
              <strong>{currentSpecialist.name}</strong>
              <small>Otonom pazarlama asistanı</small>
            </span>
          </button>
        </div>

        <div className="sidebar-group">
          <p className="sidebar-heading">Sohbet Geçmişi</p>
          <label className="sidebar-search">
            <span>⌕</span>
            <input type="text" value="" readOnly placeholder="Konuşmalarda ara..." />
          </label>
          <button type="button" className="history-card">
            <img
              src={specialistAvatar}
              alt={`${currentSpecialist.name} avatarı`}
              className="dm-avatar-image subtle"
            />
            <span>
              <strong>{historyTitle}</strong>
              <small>{selectedGoals.slice(0, 2).join(' • ') || 'Başlangıç oturumu'}</small>
            </span>
          </button>
          <button type="button" className="history-link">
            Tüm konuşmaları gör
          </button>
        </div>

        <nav className="sidebar-links" aria-label="Workspace utility links">
          <button type="button" className="sidebar-link">
            Dosyalar
          </button>
          <button type="button" className="sidebar-link">
            Profilin
          </button>
          <button type="button" className="sidebar-link">
            Entegrasyonlar
          </button>
          <button type="button" className="sidebar-link">
            Paylaş & Kazan
          </button>
          <button type="button" className="sidebar-link">
            Bize Ulaş
          </button>
        </nav>

        <div className="sidebar-footer">
          <div className="workspace-user-row">
            <span className="workspace-user-dot">O</span>
            <span>{userLabel}</span>
          </div>
          <div className="workspace-footer-actions">
            <button type="button" className="ghost-button compact-button" onClick={onRestart}>
              Baştan başla
            </button>
            <button
              type="button"
              className="ghost-button compact-button"
              onClick={isGuest ? onOpenAuth : onSignOut}
            >
              {isGuest ? 'Giriş yap' : 'Çıkış yap'}
            </button>
          </div>
        </div>
      </aside>

      <main className="chat-panel">
        <div className="chat-room-header">
          <strong>#main</strong>
          <span className="date-pill">{dateLabel}</span>
        </div>

        <div className="panel-header">
          <div>
            <p className="mini-label">{workspaceTitle}</p>
            <h1>{analysis.companyName}</h1>
          </div>

          <div className="panel-header-actions">
            {isGuest ? (
              <button type="button" className="ghost-button compact-button" onClick={onOpenAuth}>
                Giriş yap
              </button>
            ) : null}
            <div className="status-badge">
              <span className="status-dot"></span>
              <span>
                {analysisPending
                  ? 'Analiz sürüyor'
                  : analysisError
                    ? 'Tekrar denenmeli'
                    : 'Hazır'}
              </span>
            </div>
          </div>
        </div>

        <div ref={chatThreadRef} className="chat-thread">
          {renderUserMessage()}
          {analysisPending || threadMessages.length === 0
            ? renderLiveThread()
            : threadMessages.map((message) => renderPersistedMessage(message))}
          {pendingChatMessage ? renderPendingUserMessage(pendingChatMessage) : null}
          {chatPending ? renderTypingIndicator() : null}
          {chatError && !analysisPending
            ? renderAssistantMessage(<p>{chatError}</p>, 'error-message')
            : null}
          {analysisError && !analysisPending && threadMessages.length > 0
            ? renderAssistantMessage(<p>{analysisError}</p>, 'error-message')
            : null}
          {shouldShowTrialCta ? (
            <div className="chat-thread-footer">{renderTrialCta()}</div>
          ) : null}
        </div>
      </main>

      <aside className="insight-panel">
        <div className="insight-card knowledge-bank-card">
          <div className="side-section-heading">
            <p className="mini-label">Marka Bilgi Bankası</p>
            <span>{memoryFiles.length || 0} dosya</span>
          </div>
          <div className="knowledge-list">
            {memoryFiles.length > 0 ? (
              knowledgeFiles.map((file) => (
                <button
                  key={file.id}
                  type="button"
                  className={`knowledge-item ${activeFileId === file.id ? 'selected' : ''}`}
                  onClick={() => onOpenFile(file.id)}
                >
                  <div>
                    <strong>{file.title}</strong>
                    <small>{file.filename}</small>
                  </div>
                  <span>&rsaquo;</span>
                </button>
              ))
            ) : (
              <div className="knowledge-empty">Dosyalar oluşturuluyor...</div>
            )}
          </div>
          {memoryFiles.length > 2 ? (
            <button
              type="button"
              className="knowledge-toggle"
              onClick={() => setShowAllKnowledgeFiles((current) => !current)}
            >
              {showAllKnowledgeFiles ? 'Daralt' : 'Genişlet'}
            </button>
          ) : null}
        </div>
      </aside>

      <div className="chat-input-bar">
        <button type="button" className="chat-plus-button" aria-label="Yeni iş">
          +
        </button>
        <input
          type="text"
          value={chatDraft}
          onChange={(event) => onChatDraftChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              onChatSubmit()
            }
          }}
          disabled={analysisPending || chatPending || isChatLocked}
          placeholder={
            isChatLocked
              ? `Bu oturum için ${CHAT_MESSAGE_LIMIT} mesaj hakkı doldu`
              : `Olric’e mesaj yaz... (${chatRemainingMessages}/${CHAT_MESSAGE_LIMIT})`
          }
        />
        <button
          type="button"
          className="chat-send-button"
          aria-label="Gönder"
          disabled={analysisPending || chatPending || isChatLocked || !chatDraft.trim()}
          onClick={onChatSubmit}
        >
          ^
        </button>
      </div>
    </section>
  )
}
