import type { Job, Preview, GenerateRequest } from '../types'

async function apiFetch(path: string, init?: RequestInit) {
  const res = await fetch(path, init)
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
