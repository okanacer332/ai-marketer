export type BrandAssets = {
  brandLogo: string | null
  favicon: string | null
  touchIcon: string | null
  socialImage: string | null
  manifestUrl: string | null
  maskIcon: string | null
  tileImage: string | null
  candidates: string[]
}

export type Analysis = {
  companyName: string
  domain: string
  logoUrl: string | null
  brandAssets: BrandAssets | null
  sector: string
  offer: string
  audience: string
  tone: string
  pricePosition: string
  competitors: string[]
  opportunity: string
  firstMonthPlan: string[]
  palette: string[]
}

export type MemoryFile = {
  id: string
  filename: string
  title: string
  blurb: string
  content: string
  version?: number | null
  isCurrent?: boolean | null
}

export type SourcePage = {
  url: string
  title: string
  description: string
  headings: string[]
  pageType: string
  fetchMode: string
  excerpt: string
}

export type FaqItem = {
  question: string
  answer: string
}

export type CrawlForm = {
  action: string
  method: string
  fields: string[]
}

export type CrawlPage = {
  url: string
  title: string
  description: string
  headings: string[]
  pageType: string
  fetchMode: string
  statusCode: number
  excerpt: string
  mainContent: string
  ctaTexts: string[]
  valueProps: string[]
  pricingSignals: string[]
  faqItems: FaqItem[]
  forms: CrawlForm[]
  entityLabels: string[]
  imageAlts: string[]
  logoCandidates: string[]
  technologies: string[]
  currencies: string[]
  zones: Record<string, string[]>
  meta: Record<string, string>
}

export type CrawlMeta = {
  status: string
  fetchStrategy: string
  pageLimit: number
  depthLimit: number
  pagesVisited: number
  pagesSucceeded: number
  pagesFailed: number
  sitemapUrls: string[]
  renderModes: string[]
  notes: string[]
}

export type ContactSignals = {
  emails: string[]
  phones: string[]
  socials: string[]
  addresses: string[]
}

export type ResearchPackage = {
  companyNameCandidates: string[]
  heroMessages: string[]
  semanticZones: Record<string, string[]>
  positioningSignals: string[]
  offerSignals: string[]
  serviceOffers: string[]
  productOffers: string[]
  audienceSignals: string[]
  trustSignals: string[]
  proofPoints: string[]
  conversionActions: string[]
  contentTopics: string[]
  seoSignals: string[]
  geographySignals: string[]
  languageSignals: string[]
  marketSignals: string[]
  visualSignals: string[]
  coreValueProps: string[]
  supportingBenefits: string[]
  proofClaims: string[]
  audienceClaims: string[]
  ctaClaims: string[]
  evidenceBlocks: Array<{
    type: string
    claim: string
    why: string
    confidence: number
    evidenceUrls: string[]
  }>
}

export type StrategicSummary = {
  positioning: string
  differentiation: string
  bestFitAudience: string
  primaryGrowthLever: string
  conversionGap: string
  contentAngle: string
}

export type QualityCheck = {
  id: string
  label: string
  passed: boolean
  detail: string
}

export type QualityReview = {
  score: number
  verdict: string
  strengths: string[]
  risks: string[]
  checks: QualityCheck[]
}

export type AnalysisMeta = {
  engine: string
  engineVersion: string
  promptVersion: string
}

export type IntegrationConnection = {
  id: string
  providerKey: string
  provider: string
  status: string
  accountLabel: string
  scopes: string[]
  authMode: string
  tokenConfigured: boolean
  lastSyncStatus: string
  lastSyncMessage: string
  lastSyncAt?: string | null
  updatedAt?: string | null
}

export type IntegrationSyncRun = {
  id: string
  providerKey: string
  provider: string
  status: string
  trigger: string
  message: string
  startedAt?: string | null
  finishedAt?: string | null
}

export type ChatAttachment = {
  type: string
  id: string
  fileId: string
  filename: string
  title: string
  blurb: string
  version?: number | null
  isCurrent?: boolean | null
}

export type ChatMessage = {
  id: string
  senderType: string
  senderId: string
  messageType: string
  content: string
  attachments: ChatAttachment[]
  metadata: Record<string, unknown>
  relatedAnalysisRunId?: string | null
  createdAt?: string | null
}

export type ChatThread = {
  id: string
  title: string
  status: string
  messages: ChatMessage[]
}

export type ChatMessageResponse = {
  chatThread: ChatThread
  remainingUserMessages: number
  maxUserMessages: number
}

export type GuestSessionResponse = {
  guestSessionId: string
  status: string
}

export type GuestSessionClaimResponse = {
  status: string
  claimedWorkspaceId?: string | null
}

export type AnalyzeResponse = {
  analysis: Analysis
  memoryFiles: MemoryFile[]
  sourcePages: SourcePage[]
  researchPackage?: ResearchPackage | null
  strategicSummary?: StrategicSummary | null
  qualityReview?: QualityReview | null
  analysisMeta?: AnalysisMeta | null
  crawlMeta?: CrawlMeta | null
  crawlPages?: CrawlPage[]
  integrationConnections?: IntegrationConnection[]
  integrationSyncRuns?: IntegrationSyncRun[]
  chatThread?: ChatThread | null
  notes: string[]
  contactSignals: ContactSignals
}

export type WorkspaceSnapshot = {
  website: string
  selectedGoals: string[]
  connectedPlatforms: string[]
  analysisResult: AnalyzeResponse
  trialActivated: boolean
  selectedSpecialist: string
}
