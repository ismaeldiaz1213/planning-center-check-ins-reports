export type Lang = 'es' | 'en'

export const strings = {
  // ── Navbar ──────────────────────────────────────────────────────────────────
  'nav.title':           { en: 'IBL Roster Administrador', es: 'IBL Roster Administrador' },
  'nav.dashboard':       { en: 'Dashboard',                es: 'Inicio' },

  // ── Home page ────────────────────────────────────────────────────────────────
  'home.heading':        { en: 'Dashboard',                es: 'Panel Principal' },
  'home.sub':            { en: 'Manage rosters, preview PDFs, and run jobs.',
                           es: 'Administra los rosters, previsualiza los PDFs y ejecuta los trabajos.' },

  // ── Tiles ────────────────────────────────────────────────────────────────────
  'tile.previews.title': { en: 'PDF Previews',             es: 'Vista Previa de PDFs' },
  'tile.previews.desc':  { en: 'Generate and view roster PDFs with mock data across all themes.',
                           es: 'Genera y visualiza los rosters en PDF con datos de prueba en todos los temas.' },

  'tile.rutas.title':    { en: 'Run Rutas',                es: 'Ejecutar Rutas' },
  'tile.rutas.desc':     { en: 'Fetch check-ins, generate rosters, and upload them to Google Drive.',
                           es: 'Obtiene los registros, genera los rosters y los sube a Google Drive.' },

  'tile.escuela.title':  { en: 'Run Escuela Dominical',    es: 'Ejecutar Escuela Dominical' },
  'tile.escuela.desc':   { en: 'Generate Sunday school rosters with route and attendance data.',
                           es: 'Genera los rosters de la Escuela Dominical con datos de rutas y asistencia.' },

  'tile.settings.title': { en: 'Edit Settings',            es: 'Editar Configuración' },
  'tile.settings.desc':  { en: 'Change themes, event weeks, and job parameters.',
                           es: 'Cambia los temas, semanas del evento y parámetros de los trabajos.' },

  'tile.upload.title':   { en: 'Upload Code',              es: 'Subir Código' },
  'tile.upload.desc':    { en: 'Build and deploy the latest code to Google Cloud Run.',
                           es: 'Compila y despliega el código más reciente a Google Cloud Run.' },

  'tile.logs.title':     { en: 'View Logs',                es: 'Ver Registros' },
  'tile.logs.desc':      { en: 'Browse recent job logs and execution history.',
                           es: 'Consulta los registros recientes de los trabajos ejecutados.' },

  'tile.cta':            { en: 'Open →',                   es: 'Abrir →' },
  'tile.soon':           { en: 'Coming Soon',              es: 'Próximamente' },

  // ── Job modal ────────────────────────────────────────────────────────────────
  'job.rutas.title':     { en: 'Run Rutas',                es: 'Ejecutar Rutas' },
  'job.rutas.desc':      { en: 'Fetches check-ins, generates Roster.pdf and Direcciones-Roster.pdf for every bus route, then uploads them to Google Drive.',
                           es: 'Obtiene los registros, genera Roster.pdf y Direcciones-Roster.pdf para cada ruta y los sube a Google Drive.' },

  'job.escuela.title':   { en: 'Run Escuela Dominical',    es: 'Ejecutar Escuela Dominical' },
  'job.escuela.desc':    { en: 'Fetches Sunday school check-ins, generates Roster.pdf with route and attendance data for each class, then uploads to Google Drive.',
                           es: 'Obtiene los registros de Escuela Dominical, genera Roster.pdf con datos de rutas y asistencia para cada clase y los sube a Google Drive.' },

  'job.run':             { en: 'Run',                      es: 'Ejecutar' },
  'job.running':         { en: 'Running…',                 es: 'Ejecutando…' },
  'job.placeholder':     { en: 'Press Run to start…',      es: 'Presiona Ejecutar para comenzar…' },

  // ── Preview modal ────────────────────────────────────────────────────────────
  'preview.title':       { en: 'PDF Previews',             es: 'Vista Previa de PDFs' },
  'preview.regenerate':  { en: 'Regenerate',               es: 'Regenerar' },
  'preview.generating':  { en: 'Generating…',              es: 'Generando…' },
  'preview.empty':       { en: 'No PDF found for',         es: 'No se encontró PDF para' },
  'preview.emptyHint':   { en: 'Click Regenerate to create it.',
                           es: 'Haz clic en Regenerar para crearlo.' },

  // ── Status badge ─────────────────────────────────────────────────────────────
  'status.idle':         { en: 'Idle',                     es: 'Inactivo' },
  'status.running':      { en: 'Running',                  es: 'Ejecutando' },
  'status.success':      { en: 'Success',                  es: 'Completado' },
  'status.failed':       { en: 'Failed',                   es: 'Error' },

  // ── Footer ───────────────────────────────────────────────────────────────────
  'footer.church':       { en: 'Iglesia Bautista Libertad', es: 'Iglesia Bautista Libertad' },
  'footer.location':     { en: 'Houston, TX',              es: 'Houston, TX' },
  'footer.rights':       { en: 'All rights reserved.',     es: 'Todos los derechos reservados.' },
} satisfies Record<string, Record<Lang, string>>

export type TranslationKey = keyof typeof strings
