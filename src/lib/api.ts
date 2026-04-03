import type { AnalyzeResponse, WorkspaceSnapshot } from '../types'
import { auth } from './firebase'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') || ''

type AnalyzePayload = {
  website: string
  goals: string[]
  connectedPlatforms: string[]
}

async function buildAuthHeaders(includeJson = false): Promise<Record<string, string>> {
  const user = auth.currentUser
  if (!user) {
    throw new Error('Oturum bulunamadı. Lütfen tekrar giriş yap.')
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

export async function analyzeWebsite(
  payload: AnalyzePayload,
): Promise<AnalyzeResponse> {
  const response = await fetch(`${API_BASE_URL}/api/analyze`, {
    method: 'POST',
    headers: await buildAuthHeaders(true),
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null

    throw new Error(errorPayload?.detail || 'Website analysis failed.')
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

    throw new Error(errorPayload?.detail || 'Workspace snapshot could not be fetched.')
  }

  return (await response.json()) as WorkspaceSnapshot
}

export async function storeWorkspaceSnapshot(
  payload: WorkspaceSnapshot,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/workspace-snapshot`, {
    method: 'POST',
    headers: await buildAuthHeaders(true),
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null

    throw new Error(errorPayload?.detail || 'Workspace snapshot could not be stored.')
  }
}
