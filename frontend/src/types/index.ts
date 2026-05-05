export type JobStatus = 'running' | 'success' | 'failed'

export interface Job {
  id: string
  type: 'rutas' | 'escuela' | 'preview'
  status: JobStatus
  output: string[]
  total_lines: number
  started_at: string
  finished_at: string | null
}

export interface Preview {
  filename: string
  theme: string
  type: string
  size_bytes: number
  url: string
}

export interface GenerateRequest {
  theme?: string
  type?: string
}
