import type { AnalyzeResponse, ChatMessageResponse, WorkspaceSnapshot } from '../types'
import { auth } from './firebase'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') || ''

type AnalyzePayload = {
  website: string
  goals: string[]
  connectedPlatforms: string[]
}

async function buildAuthHeaders(includeJson = false): Promise<Record<string, string>> {
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
