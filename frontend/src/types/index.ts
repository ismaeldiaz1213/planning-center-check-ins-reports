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

export interface Settings {
  pco_app_id: string
  pco_secret: string
  google_drive_parent_folder_id: string
  rutas_weeks: number
  rutas_theme: string
  escuela_weeks: number
  escuela_theme: string
}

export interface SettingsWrite {
  pco_app_id?: string
  pco_secret?: string
  google_drive_parent_folder_id?: string
  rutas_weeks?: number
  rutas_theme?: string
  escuela_weeks?: number
  escuela_theme?: string
}
