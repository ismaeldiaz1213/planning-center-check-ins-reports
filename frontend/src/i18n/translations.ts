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
  'preview.title':               { en: 'PDF Previews',             es: 'Vista Previa de PDFs' },
  'preview.regenerate':          { en: 'Regenerate',               es: 'Regenerar' },
  'preview.generating':          { en: 'Generating…',              es: 'Generando…' },
  'preview.empty':               { en: 'No PDF found for',         es: 'No se encontró PDF para' },
  'preview.emptyHint':           { en: 'Click Regenerate to create it.',
                                   es: 'Haz clic en Regenerar para crearlo.' },

  // Preview — seasons (theme tabs)
  'preview.theme.default':       { en: 'Default',    es: 'Predeterminado' },
  'preview.theme.primavera':     { en: 'Primavera',  es: 'Primavera'      },
  'preview.theme.verano':        { en: 'Verano',     es: 'Verano'         },
  'preview.theme.otono':         { en: 'Otoño',      es: 'Otoño'          },
  'preview.theme.invierno':      { en: 'Invierno',   es: 'Invierno'       },

  // Preview — pdf type buttons
  'preview.type.roster':         { en: 'Roster',       es: 'Roster'       },
  'preview.type.escuela':        { en: 'Escuela',      es: 'Escuela'      },
  'preview.type.direcciones':    { en: 'Direcciones',  es: 'Direcciones'  },

  // ── Settings modal ───────────────────────────────────────────────────────────
  'settings.title':              { en: 'Edit Settings',               es: 'Editar Configuración'          },
  'settings.section.creds':      { en: 'PCO Credentials',             es: 'Credenciales PCO'              },
  'settings.pco_app_id':         { en: 'PCO App ID',                  es: 'ID de App PCO'                 },
  'settings.pco_secret':         { en: 'PCO Secret',                  es: 'Secreto PCO'                   },
  'settings.section.drive':      { en: 'Google Drive',                es: 'Google Drive'                  },
  'settings.drive_folder':       { en: 'Parent Folder ID',            es: 'ID de Carpeta Padre'           },
  'settings.section.rutas':      { en: 'Rutas Job Defaults',          es: 'Valores por Defecto – Rutas'   },
  'settings.section.escuela':    { en: 'Escuela Dominical Defaults',  es: 'Valores por Defecto – Escuela' },
  'settings.weeks':              { en: 'Recent weeks to include',     es: 'Semanas recientes a incluir'   },
  'settings.theme':              { en: 'Campaign theme',              es: 'Tema de campaña'               },
  'settings.theme.none':         { en: 'None (default)',              es: 'Ninguno (predeterminado)'      },
  'settings.save':               { en: 'Save',                        es: 'Guardar'                       },
  'settings.saving':             { en: 'Saving…',                     es: 'Guardando…'                    },
  'settings.saved':              { en: 'Saved!',                      es: '¡Guardado!'                    },
  'settings.error':              { en: 'Failed to save settings.',    es: 'Error al guardar la configuración.' },

  // ── Logs modal ────────────────────────────────────────────────────────────────
  'logs.title':                  { en: 'Job Logs',                    es: 'Registros de Trabajos'         },
  'logs.refresh':                { en: 'Refresh',                     es: 'Actualizar'                    },
  'logs.empty':                  { en: 'No jobs have been run yet.',  es: 'No se han ejecutado trabajos aún.' },
  'logs.type.rutas':             { en: 'Rutas',                       es: 'Rutas'                         },
  'logs.type.escuela':           { en: 'Escuela Dominical',           es: 'Escuela Dominical'             },
  'logs.type.preview':           { en: 'Preview',                     es: 'Vista Previa'                  },
  'logs.started':                { en: 'Started',                     es: 'Iniciado'                      },
  'logs.duration':               { en: 'Duration',                    es: 'Duración'                      },
  'logs.output':                 { en: 'Output',                      es: 'Salida'                        },
  'logs.noOutput':               { en: 'No output.',                  es: 'Sin salida.'                   },

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
