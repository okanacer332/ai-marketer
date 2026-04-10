param(
    [string]$GcloudPath = "$env:LOCALAPPDATA\\Google\\Cloud SDK\\google-cloud-sdk\\bin\\gcloud.cmd",
    [string]$ProjectId,
    [string]$Region = "europe-west1",
    [string]$ServiceName = "ai-marketer-backend",
    [string]$RepositoryName = "ai-marketer",
    [string]$ImageName = "backend",
    [string]$FrontendOrigin = "https://ai-marketer-hhto.vercel.app",
    [string]$FrontendOrigins = "https://ai-marketer-hhto.vercel.app,http://localhost:5173,http://127.0.0.1:5173",
    [string]$MongoDbUri = "",
    [string]$MongoDbName = "acrtech_ai_marketer",
    [string]$GeminiApiKey = "",
    [string]$GeminiModel = "gemini-2.5-flash",
    [string]$FirebaseProjectId = "ai-marketer-242f8"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $ProjectId) {
    throw "ProjectId zorunlu."
}

if (-not (Test-Path $GcloudPath)) {
    throw "gcloud bulunamadı: $GcloudPath"
}

if (-not $MongoDbUri) {
    throw "MongoDbUri zorunlu."
}

if (-not $GeminiApiKey) {
    throw "GeminiApiKey zorunlu."
}

$image = "$Region-docker.pkg.dev/$ProjectId/$RepositoryName/$ImageName`:latest"

$repoExists = $false
try {
    & $GcloudPath artifacts repositories describe $RepositoryName --location $Region --project $ProjectId *> $null
    $repoExists = $true
} catch {
    $repoExists = $false
}

if (-not $repoExists) {
    & $GcloudPath artifacts repositories create $RepositoryName `
        --repository-format=docker `
        --location=$Region `
        --description="AI Marketer backend images" `
        --project $ProjectId
}

& $GcloudPath builds submit . `
    --project $ProjectId `
    --region $Region `
    --config cloudbuild.cloudrun.yaml `
    --substitutions "_IMAGE=$image"

$envVars = @(
    "GEMINI_API_KEY=$GeminiApiKey"
    "GEMINI_MODEL=$GeminiModel"
    "FRONTEND_ORIGIN=$FrontendOrigin"
    "FRONTEND_ORIGINS=$FrontendOrigins"
    "HTTP_VERIFY_SSL=true"
    "MONGODB_URI=$MongoDbUri"
    "MONGODB_DB_NAME=$MongoDbName"
    "FIREBASE_PROJECT_ID=$FirebaseProjectId"
) -join ","

& $GcloudPath run deploy $ServiceName `
    --project $ProjectId `
    --region $Region `
    --image $image `
    --allow-unauthenticated `
    --port 8080 `
    --cpu 1 `
    --memory 512Mi `
    --concurrency 8 `
    --timeout 300 `
    --min-instances 0 `
    --max-instances 1 `
    --set-env-vars $envVars
