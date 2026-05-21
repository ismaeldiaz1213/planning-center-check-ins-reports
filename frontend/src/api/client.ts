import type { Job, Preview, GenerateRequest, Settings, SettingsWrite } from '../types'

let _authToken: string | null = null

export function setAuthToken(token: string | null) {
  _authToken = token
}

async function apiFetch(path: string, init?: RequestInit) {
  const authHeaders: Record<string, string> = _authToken
    ? { Authorization: `Bearer ${_authToken}` }
    : {}
  const res = await fetch(path, {
    ...init,
    headers: { ...authHeaders, ...(init?.headers as Record<string, string>) },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(text || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function fetchPreviews(): Promise<{ previews: Preview[] }> {
  return apiFetch('/api/previews')
}

export async function generatePreview(req: GenerateRequest): Promise<{ job_id: string }> {
  return apiFetch('/api/previews/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
}

export async function fetchJob(jobId: string, since = 0): Promise<Job> {
  return apiFetch(`/api/jobs/${jobId}?since=${since}`)
}

export async function runJob(type: 'rutas' | 'escuela'): Promise<{ job_id: string }> {
  return apiFetch(`/api/jobs/${type}/run`, { method: 'POST' })
}

export async function fetchSettings(): Promise<Settings> {
  return apiFetch('/api/settings')
}

export async function saveSettings(body: SettingsWrite): Promise<{ ok: boolean }> {
  return apiFetch('/api/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function fetchJobs(): Promise<{ jobs: Job[] }> {
  return apiFetch('/api/jobs')
}
