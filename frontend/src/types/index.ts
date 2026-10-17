export type JobStatus = 'running' | 'success' | 'failed'

export interface Job {
  /** Report id (e.g. 'rutas', 'escuela-b') or 'preview'. Open-ended: reports are
   *  configured in reports.yaml on the backend, not enumerated here. */
  type: string
  id: string
  status: JobStatus
  output: string[]
  total_lines: number
  started_at: string
  finished_at: string | null
}

/** One report configured in the backend's reports.yaml. */
export interface Report {
  id: string
  label: string
  icon: string
  outputs: string[]
  show_route: boolean
  default_weeks: number
  default_theme: string
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

export interface ReportSettings {
  label: string
  weeks: number
  theme: string
}

export interface Settings {
  pco_app_id: string
  pco_secret: string
  google_drive_parent_folder_id: string
  /** Per-report run defaults, keyed by report id. */
  reports: Record<string, ReportSettings>
}

export interface ReportSettingsWrite {
  weeks?: number
  theme?: string
}

export interface SettingsWrite {
  pco_app_id?: string
  pco_secret?: string
  google_drive_parent_folder_id?: string
  reports?: Record<string, ReportSettingsWrite>
}
