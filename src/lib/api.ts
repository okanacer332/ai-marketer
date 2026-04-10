import type {
  AnalyzeResponse,
  ChatMessageResponse,
  GuestSessionClaimResponse,
  GuestSessionResponse,
  WorkspaceSnapshot,
} from '../types'
import { auth } from './firebase'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ||
  'https://ai-marketer-backend-5jzmdzz6lq-ew.a.run.app'

type AnalyzePayload = {
  website: string
  goals: string[]
  connectedPlatforms: string[]
}

function buildGuestHeaders(guestSessionId: string, includeJson = false): Record<string, string> {
  if (!guestSessionId.trim()) {
    throw new Error('Misafir oturumu bulunamadı.')
  }

  const headers: Record<string, string> = {
    'X-Guest-Session-ID': guestSessionId.trim(),
  }

  if (includeJson) {
    headers['Content-Type'] = 'application/json'
  }

  return headers
}

async function buildAuthHeaders(includeJson = false): Promise<Record<string, string>> {
  if (!auth) {
    throw new Error('Giriş şu an yapılandırılmadı.')
  }

  const user = auth.currentUser
  if (!user) {
    throw new Error('Oturum bulunamadı. Lütfen tekrar giriş yapın.')
  }

  const token = await user.getIdToken()
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
  }

  if (includeJson) {
    headers['Content-Type'] = 'application/json'
  }

  return headers
}

export async function analyzeWebsite(payload: AnalyzePayload): Promise<AnalyzeResponse> {
  const response = await fetch(`${API_BASE_URL}/api/analyze`, {
    method: 'POST',
    headers: await buildAuthHeaders(true),
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null

    throw new Error(errorPayload?.detail || 'Website analizi tamamlanamadı.')
  }

  return (await response.json()) as AnalyzeResponse
}

export async function createGuestSession(): Promise<GuestSessionResponse> {
  const response = await fetch(`${API_BASE_URL}/api/guest-session`, {
    method: 'POST',
  })

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null

    throw new Error(errorPayload?.detail || 'Misafir oturumu oluşturulamadı.')
  }

  return (await response.json()) as GuestSessionResponse
}

export async function analyzeGuestWebsite(
  payload: AnalyzePayload,
  guestSessionId: string,
): Promise<AnalyzeResponse> {
  const response = await fetch(`${API_BASE_URL}/api/analyze-guest`, {
    method: 'POST',
    headers: buildGuestHeaders(guestSessionId, true),
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null

    throw new Error(errorPayload?.detail || 'Analiz başlatılamadı.')
  }

  return (await response.json()) as AnalyzeResponse
}

export async function fetchWorkspaceSnapshot(): Promise<WorkspaceSnapshot | null> {
  const response = await fetch(`${API_BASE_URL}/api/workspace-snapshot`, {
    headers: await buildAuthHeaders(false),
  })

  if (response.status === 404) {
    return null
  }

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null

    throw new Error(errorPayload?.detail || 'Çalışma alanı verisi alınamadı.')
  }

  return (await response.json()) as WorkspaceSnapshot
}

export async function fetchGuestWorkspaceSnapshot(
  guestSessionId: string,
): Promise<WorkspaceSnapshot | null> {
  const response = await fetch(`${API_BASE_URL}/api/workspace-snapshot-guest`, {
    headers: buildGuestHeaders(guestSessionId, false),
  })

  if (response.status === 404) {
    return null
  }

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null

    throw new Error(errorPayload?.detail || 'Misafir çalışma alanı alınamadı.')
  }

  return (await response.json()) as WorkspaceSnapshot
}

export async function storeWorkspaceSnapshot(payload: WorkspaceSnapshot): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/workspace-snapshot`, {
    method: 'POST',
    headers: await buildAuthHeaders(true),
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null

    throw new Error(errorPayload?.detail || 'Çalışma alanı verisi kaydedilemedi.')
  }
}

export async function sendChatMessage(message: string): Promise<ChatMessageResponse> {
  const response = await fetch(`${API_BASE_URL}/api/chat-message`, {
    method: 'POST',
    headers: await buildAuthHeaders(true),
    body: JSON.stringify({ message }),
  })

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null

    throw new Error(errorPayload?.detail || 'Mesaj gönderilemedi.')
  }

  return (await response.json()) as ChatMessageResponse
}

export async function sendGuestChatMessage(
  message: string,
  guestSessionId: string,
): Promise<ChatMessageResponse> {
  const response = await fetch(`${API_BASE_URL}/api/chat-message-guest`, {
    method: 'POST',
    headers: buildGuestHeaders(guestSessionId, true),
    body: JSON.stringify({ message }),
  })

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null

    throw new Error(errorPayload?.detail || 'Mesaj gönderilemedi.')
  }

  return (await response.json()) as ChatMessageResponse
}

export async function claimGuestWorkspace(
  guestSessionId: string,
): Promise<GuestSessionClaimResponse> {
  const response = await fetch(`${API_BASE_URL}/api/guest-session/claim`, {
    method: 'POST',
    headers: {
      ...(await buildAuthHeaders(false)),
      ...buildGuestHeaders(guestSessionId, false),
    },
  })

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null

    throw new Error(errorPayload?.detail || 'Misafir çalışma alanı hesaba bağlanamadı.')
  }

  return (await response.json()) as GuestSessionClaimResponse
}
