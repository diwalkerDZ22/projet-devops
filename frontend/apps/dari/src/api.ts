/**
 * Accès à l'API Dari : le client du kit (token et refresh gérés) + TanStack Query.
 * Les clés de requête sont centralisées ici pour invalider précisément après une modification.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { QueryKey } from '@tanstack/react-query'

import { ApiError } from '@auth-kit/react/client'
import type { RequestOptions } from '@auth-kit/react/client'
import { useAuthClient } from '@auth-kit/react/react'

export const K = {
  moi: ['dari', 'moi'] as const,
  ref: (nom: string) => ['dari', 'ref', nom] as const,
  sessions: ['dari', 'sessions'] as const,
  session: (id: number) => ['dari', 'session', id] as const,
  epreuves: (id: number) => ['dari', 'session', id, 'epreuves'] as const,
  modules: (id: number) => ['dari', 'session', id, 'modules'] as const,
  feuille: (sid: number, mid: number) => ['dari', 'session', sid, 'notes', mid] as const,
  deliberation: (id: number) => ['dari', 'session', id, 'deliberation'] as const,
  stats: (id: number) => ['dari', 'session', id, 'stats'] as const,
  mesResultats: ['dari', 'mes-resultats'] as const,
  reclamations: ['dari', 'reclamations'] as const,
}

/** GET typé ; enabled=false tant qu'un paramètre manque. */
export function useGet<T>(key: QueryKey, path: string, options: { enabled?: boolean; query?: RequestOptions['query'] } = {}) {
  const client = useAuthClient()
  return useQuery({
    queryKey: options.query ? [...key, options.query] : key,
    queryFn: () => client.request<T>(path, { query: options.query }),
    enabled: options.enabled ?? true,
  })
}

/** Mutation qui invalide les clés données une fois réussie. */
export function useSend<TBody = unknown, TResult = unknown>(
  method: string,
  path: string | ((body: TBody) => string),
  invalidate: QueryKey[] = [],
) {
  const client = useAuthClient()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: TBody) => {
      const url = typeof path === 'function' ? path(body) : path
      const options: RequestOptions = { method }
      if (body instanceof FormData) options.body = body
      else if (body !== undefined && body !== null) options.json = body
      return client.request<TResult>(url, options)
    },
    onSuccess: () => Promise.all(invalidate.map((queryKey) => queryClient.invalidateQueries({ queryKey }))),
  })
}

/** Ouvre un PDF protégé (le token est dans l'en-tête, un simple lien ne suffit pas). */
export function useOpenPdf() {
  const client = useAuthClient()
  return async (path: string) => {
    const blob = await client.request<Blob>(path, { responseType: 'blob' })
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank', 'noopener')
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  }
}

/** Message affichable d'une erreur de l'API (format {code, message} du backend). */
export function messageErreur(error: unknown): string {
  if (error instanceof ApiError) {
    const champs = Object.entries(error.fields ?? {})
    return champs.length ? `${error.message} ${champs.map(([k, v]) => `${k} : ${v}`).join(' ; ')}` : error.message
  }
  return 'Erreur inattendue, réessayez.'
}

export function estErreur(error: unknown, code: string): boolean {
  return error instanceof ApiError && error.code === code
}
