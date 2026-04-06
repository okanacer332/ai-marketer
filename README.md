# Acrtech AI Marketer

Chat-first onboarding and autonomous marketing workspace for local e-commerce brands.

## Stack

- Frontend: React 19 + TypeScript + Vite
- Auth: Firebase Auth with Google + email/password
- Analysis API: FastAPI
- Scraping: local `Scrapling-main` project
- Synthesis: Gemini API on the backend
- Database: MongoDB
- Runtime: Docker Compose

## Architecture

The app now runs in a hybrid development setup:

- `frontend`
  Local Vite development server exposed on `http://localhost:5173`
- `backend`
  FastAPI service inside Docker exposed on `http://localhost:8000`
- `mongodb`
  MongoDB inside Docker exposed on `mongodb://localhost:27017`

Firebase continues to handle user authentication in the frontend. The backend stores workspace state and analysis history in MongoDB, keyed by Firebase user identity (`uid` + normalized email).

## Database Design

MongoDB database name:

- `acrtech_ai_marketer`

Collections:

- `users`
  Authenticated application users synced from Firebase identity
- `workspaces`
  Current workspace container and active pointers
- `workspace_members`
  Membership and role mapping between users and workspaces
- `websites`
  Website context attached to a workspace
- `crawl_runs`
  Each Scrapling crawl execution with strategy, status, and page counts
- `crawled_pages`
  Page-level crawl evidence captured from Scrapling
- `analysis_runs`
  Historical analysis snapshots for audit and iteration
- `memory_documents`
  Versioned markdown memory files generated from analyses
- `integration_connections`
  Workspace bazli platform baglanti kayitlari ve son sync durumu
- `integration_sync_runs`
  Her provider icin sync denemesi, atlama veya hata gecmisi
- `audit_events`
  Istek, analiz ve workspace operasyonlari icin izlenebilir olay kayitlari
- `chat_threads`
  Conversation threads inside a workspace
- `chat_messages`
  Timeline and attachment-rich messages for Aylin and system events

Legacy:

- `workspace_snapshots`
  Old snapshot store kept only for fallback migration

Key workspace fields:

- `ownerUserId`
- `ownerFirebaseUid`
- `name`
- `slug`
- `selectedSpecialist`
- `currentState`
- `currentWebsiteId`
- `latestCrawlRunId`
- `latestAnalysisRunId`
- `createdAt`
- `updatedAt`
- `lastAnalysisAt`

Indexes:

- unique index on `users.firebaseUid`
- unique sparse index on `users.emailNormalized`
- workspace index on `workspaces(ownerUserId, updatedAt desc)`
- unique index on `workspaces.slug`
- unique compound index on `workspace_members(workspaceId, userId)`
- unique compound index on `websites(workspaceId, domain)`
- history index on `crawl_runs(workspaceId, createdAt desc)`
- page index on `crawled_pages(crawlRunId, pageIndex)`
- history index on `analysis_runs(workspaceId, createdAt desc)`
- current-version index on `memory_documents(workspaceId, websiteId, kind, isCurrent)`
- sequence index on `chat_messages(threadId, sequence)`

## Environment

Frontend env:

- `.env.local`

Backend env:

- `backend/.env`

Examples:

- `.env.example`
- `backend/.env.example`

Important backend env variables:

- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `FRONTEND_ORIGIN`
- `HTTP_VERIFY_SSL`
- `MONGODB_URI`
- `MONGODB_DB_NAME`

## Vercel Frontend Deploy

Bu repo Vercel tarafında sadece frontend deploy edecek şekilde hazırlandı.

Gerekli dosyalar:

- [vercel.json](C:/Users/acero/Documents/GitHub/ai-marketer/vercel.json)
- [.vercelignore](C:/Users/acero/Documents/GitHub/ai-marketer/.vercelignore)

Vercel ortam değişkenleri:

- `VITE_FIREBASE_API_KEY`
- `VITE_FIREBASE_AUTH_DOMAIN`
- `VITE_FIREBASE_PROJECT_ID`
- `VITE_FIREBASE_STORAGE_BUCKET`
- `VITE_FIREBASE_MESSAGING_SENDER_ID`
- `VITE_FIREBASE_APP_ID`
- `VITE_FIREBASE_MEASUREMENT_ID`
- `VITE_API_BASE_URL`

Notlar:

- `VITE_API_BASE_URL` Vercel'de canlı backend adresinize işaret etmelidir.
- SPA yönlendirmeleri için tüm yollar `index.html`'e rewrite edilir.
- `/basla`, `/hedefler`, `/baglantilar` ve `/calisma-alani` yolları doğrudan açıldığında frontend doğru ekranı yükler.

## Run

Recommended:

- [calistir.bat](C:/Users/acero/Documents/GitHub/ai-marketer/calistir.bat)

Quick shortcuts:

- [calistir.bat](C:/Users/acero/Documents/GitHub/ai-marketer/kısayollar/calistir.bat)
- [db-sifirla.bat](C:/Users/acero/Documents/GitHub/ai-marketer/kısayollar/db-sifirla.bat)

What `calistir.bat` does:

- validates Docker and required env files
- installs frontend dependencies if `node_modules` is missing
- removes old Docker frontend leftovers if they exist
- builds and starts `backend` and `mongodb`
- starts the Vite frontend locally on `http://localhost:5173`
- waits for backend and frontend health
- opens the app in your browser

## Reset Database

Use:

- [db-sifirla.bat](C:/Users/acero/Documents/GitHub/ai-marketer/db-sifirla.bat)

What it resets:

- MongoDB volume `acrtech_mongodb_data`
- legacy file store `backend/data/workspace_snapshots.json` if it still exists

What it does not reset:

- Firebase accounts
- browser tarafindaki Firebase session verisi
- local Vite frontend process

## What the backend does

The `/api/analyze` endpoint:

- normalizes the submitted URL
- crawls the homepage plus selected internal pages with Scrapling
- upgrades fetch mode from static to dynamic or stealth when necessary
- extracts content, structure, pricing, FAQ, CTA, contact, logo, and technology signals
- returns structured `crawlMeta` and detailed `crawlPages` payloads alongside the marketing analysis
- returns `integrationConnections` and `integrationSyncRuns` preview payloads for selected providers
- returns an ephemeral `chatThread` payload so the workspace can open with the same message model immediately
- sends the research bundle to Gemini for structured analysis
- falls back to heuristic analysis if Gemini is unavailable
- writes audit events and structured JSON logs with crawl/synthesis durations

The `/api/workspace-snapshot` endpoints:

- read the active workspace by resolving `user -> defaultWorkspaceId -> currentWebsiteId/latestAnalysisRunId`
- persist current workspace state into `workspaces`, `websites`, `crawl_runs`, `crawled_pages`, `analysis_runs`, `memory_documents`, `integration_connections`, `integration_sync_runs`, `chat_threads`, and `chat_messages`
- maintain analysis history through `analysis_runs`
- rebuild the latest workspace response by joining analysis data with crawl history
- rebuild memory files from `memory_documents` so markdown docs are versioned outside the main analysis blob
- rebuild integration state from `integration_connections` and recent `integration_sync_runs`
- rebuild the workspace timeline from `chat_threads` and `chat_messages`
- migrate legacy `workspace_snapshots` data on demand when encountered
- write audit events for snapshot reads and writes

The `/api/ops/recent-events` endpoint:

- returns the latest `audit_events` for the authenticated user's active workspace
- helps inspect recent analysis, snapshot, and operational flows without opening MongoDB directly

## Observability

- every API request is logged as structured JSON with `requestId`, path, status code, and duration
- analysis flow logs include crawl duration, synthesis duration, total duration, and engine metadata
- workspace restore and persist flows emit both structured logs and persisted `audit_events`

## Verification

- `npm run build`
- `npm run lint`
- `backend\\.venv\\Scripts\\python -m compileall backend\\app`
- `docker compose config`
