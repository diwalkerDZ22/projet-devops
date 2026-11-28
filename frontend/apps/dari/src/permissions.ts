/** Codes de permission de Dari (miroir de backend/app/roles.py). */
export const P = {
  admin: 'users:manage',
  referentielLire: 'referentiel:lire',
  referentielGerer: 'referentiel:gerer',
  planningGerer: 'planning:gerer',
  sujetsDeposer: 'sujets:deposer',
  notesSaisir: 'notes:saisir',
  notesGerer: 'notes:gerer',
  deliberationGerer: 'deliberation:gerer',
  deliberationValider: 'deliberation:valider',
  resultatsConsulter: 'resultats:consulter',
  reclamationsDeposer: 'reclamations:deposer',
  reclamationsTraiter: 'reclamations:traiter',
  reclamationsGerer: 'reclamations:gerer',
  statsConsulter: 'stats:consulter',
} as const
