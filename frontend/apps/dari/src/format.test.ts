import { describe, expect, it } from 'vitest'

import { note, noteValide, parseNote } from './format'

describe('saisie des notes', () => {
  it('accepte la virgule et le champ vide', () => {
    expect(parseNote('12,5')).toBe(12.5)
    expect(parseNote(' 14 ')).toBe(14)
    expect(parseNote('')).toBeNull()
    expect(parseNote('abc')).toBeNaN()
  })

  it('valide le barème au centième, malgré les arrondis flottants', () => {
    for (const ok of [0, 10, 20, 12.35, 9.99, 0.01, null]) expect(noteValide(ok)).toBe(true)
    for (const ko of [-0.5, 20.01, 12.345, Number.NaN]) expect(noteValide(ko)).toBe(false)
  })

  it('affiche les notes avec deux décimales', () => {
    expect(note('13.7')).toBe('13.70')
    expect(note(null)).toBe('–')
  })
})
