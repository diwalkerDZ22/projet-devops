/** Libellés et mise en forme partagés par les pages. */

export const DECISIONS: Record<string, { label: string; tone: 'green' | 'amber' | 'red' }> = {
  admis: { label: 'Admis', tone: 'green' },
  rattrapage: { label: 'Rattrapage', tone: 'amber' },
  ajourne: { label: 'Ajourné', tone: 'red' },
}

export const STATUTS_SESSION: Record<string, { label: string; tone: 'indigo' | 'amber' | 'green' }> = {
  ouverte: { label: 'Ouverte', tone: 'indigo' },
  deliberee: { label: 'Délibérée', tone: 'amber' },
  publiee: { label: 'Publiée', tone: 'green' },
}

export const STATUTS_RECLAMATION: Record<string, { label: string; tone: 'gray' | 'indigo' | 'green' | 'red' }> = {
  deposee: { label: 'Déposée', tone: 'gray' },
  en_cours: { label: 'En cours', tone: 'indigo' },
  acceptee: { label: 'Acceptée', tone: 'green' },
  rejetee: { label: 'Rejetée', tone: 'red' },
}

export function note(valeur: string | number | null | undefined): string {
  if (valeur === null || valeur === undefined || valeur === '') return '–'
  return Number(valeur).toFixed(2)
}

export function date(valeur: string): string {
  return new Date(valeur.length === 10 ? `${valeur}T00:00:00` : valeur).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

export function dateHeure(valeur: string): string {
  return new Date(valeur).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
}

export function heure(valeur: string): string {
  return valeur.slice(0, 5)
}

/** Champ texte vide -> null ; sinon nombre (virgule acceptée). */
export function parseNote(texte: string): number | null {
  const propre = texte.trim().replace(',', '.')
  if (propre === '') return null
  const n = Number(propre)
  return Number.isFinite(n) ? n : Number.NaN
}

export function noteValide(n: number | null): boolean {
  // au centième près, avec une tolérance : 12.35 * 100 vaut 1234.9999999999998 en flottant
  return n === null || (!Number.isNaN(n) && n >= 0 && n <= 20 && Math.abs(Math.round(n * 100) - n * 100) < 1e-6)
}
