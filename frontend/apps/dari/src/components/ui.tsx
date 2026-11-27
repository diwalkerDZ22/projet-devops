/** Composants de mise en page de Dari, construits sur les variables --ak-* du kit (thème clair / sombre). */
import type { ReactNode } from 'react'

import { Alert, Badge, Spinner } from '@auth-kit/react/ui'

import { messageErreur } from '../api'

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="dari-page-head">
      <div>
        <h1 className="dari-page-title">{title}</h1>
        {subtitle && <p className="dari-page-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="dari-actions">{actions}</div>}
    </header>
  )
}

export function Card({ title, actions, children }: { title?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="dari-card">
      {(title || actions) && (
        <div className="dari-card-head">
          {title && <h2 className="dari-card-title">{title}</h2>}
          {actions && <div className="dari-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  )
}

/** Chargement, erreur ou contenu d'une requête. */
export function Etat<T>({
  query,
  children,
}: {
  query: { isPending: boolean; error: unknown; data: T | undefined }
  children: (data: T) => ReactNode
}) {
  if (query.error) return <Alert>{messageErreur(query.error)}</Alert>
  if (query.isPending || query.data === undefined) {
    return (
      <div className="dari-loading" role="status">
        <Spinner /> Chargement…
      </div>
    )
  }
  return <>{children(query.data)}</>
}

export function Vide({ children }: { children: ReactNode }) {
  return <p className="dari-empty">{children}</p>
}

export interface Colonne<T> {
  titre: string
  rendu: (ligne: T) => ReactNode
  align?: 'right' | 'center'
}

export function Tableau<T>({
  colonnes,
  lignes,
  cle,
  vide = 'Aucun élément.',
}: {
  colonnes: Colonne<T>[]
  lignes: T[]
  cle: (ligne: T) => string | number
  vide?: string
}) {
  if (!lignes.length) return <Vide>{vide}</Vide>
  return (
    <div className="dari-table-wrap">
      <table className="dari-table">
        <thead>
          <tr>
            {colonnes.map((c) => (
              <th key={c.titre} className={c.align ? `is-${c.align}` : undefined} scope="col">
                {c.titre}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lignes.map((ligne) => (
            <tr key={cle(ligne)}>
              {colonnes.map((c) => (
                <td key={c.titre} className={c.align ? `is-${c.align}` : undefined}>
                  {c.rendu(ligne)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Onglets<K extends string>({
  onglets,
  actif,
  onChange,
}: {
  onglets: { id: K; label: string }[]
  actif: K
  onChange: (id: K) => void
}) {
  return (
    <div className="dari-tabs" role="tablist">
      {onglets.map((o) => (
        <button
          key={o.id}
          type="button"
          role="tab"
          aria-selected={o.id === actif}
          className={`dari-tab${o.id === actif ? ' is-active' : ''}`}
          onClick={() => onChange(o.id)}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Statut({ map, valeur }: { map: Record<string, { label: string; tone: string }>; valeur: string }) {
  const s = map[valeur] ?? { label: valeur, tone: 'gray' }
  return <Badge tone={s.tone as 'gray'}>{s.label}</Badge>
}

export function Chiffre({ label, valeur, detail }: { label: string; valeur: ReactNode; detail?: ReactNode }) {
  return (
    <div className="dari-stat">
      <span className="dari-stat-label">{label}</span>
      <strong className="dari-stat-value">{valeur}</strong>
      {detail && <span className="dari-stat-detail">{detail}</span>}
    </div>
  )
}

/** Histogramme horizontal simple (CSS), accessible : chaque barre porte sa valeur en texte. */
export function Barres({ donnees, suffixe = '' }: { donnees: { label: string; valeur: number }[]; suffixe?: string }) {
  const max = Math.max(1, ...donnees.map((d) => d.valeur))
  return (
    <ul className="dari-bars">
      {donnees.map((d) => (
        <li key={d.label} className="dari-bar-row">
          <span className="dari-bar-label">{d.label}</span>
          <span className="dari-bar-track">
            <span className="dari-bar-fill" style={{ width: `${(d.valeur / max) * 100}%` }} />
          </span>
          <span className="dari-bar-value">
            {d.valeur}
            {suffixe}
          </span>
        </li>
      ))}
    </ul>
  )
}

/** Champ select stylé comme les champs du kit. */
export function Choix({
  label,
  value,
  onChange,
  options,
  vide,
  name,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  options: { value: string | number; label: string }[]
  vide?: string
  name?: string
}) {
  return (
    <label className="dari-field">
      <span className="ak-label">{label}</span>
      <select className="ak-select" name={name} value={value} onChange={(e) => onChange(e.target.value)}>
        {vide !== undefined && <option value="">{vide}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  )
}

/** Champ texte simple (formulaires de référentiels). */
export function Saisie({
  label,
  value,
  onChange,
  type = 'text',
  ...props
}: {
  label: string
  value: string
  onChange: (v: string) => void
  type?: string
  required?: boolean
  min?: number
  max?: number
  step?: number | string
  name?: string
  placeholder?: string
}) {
  return (
    <label className="dari-field">
      <span className="ak-label">{label}</span>
      <input className="ak-input" type={type} value={value} onChange={(e) => onChange(e.target.value)} {...props} />
    </label>
  )
}
