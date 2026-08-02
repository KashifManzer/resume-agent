import { describe, expect, test } from 'vitest'

import { planFill } from '../src/content/plan'
import type { Canonical, Descriptor, Mapping, Profile } from '../src/shared/types'

const profile: Profile = {
  name: 'Ada Lovelace',
  email: 'ada@analytical.io',
  phone: '555-0100',
  location: 'London, UK',
  work_auth: 'Authorized to work in the UK',
  links: {
    linkedin: 'https://linkedin.com/in/ada',
    github: 'https://github.com/ada',
    portfolio: 'https://ada.dev',
  },
}

function d(field_ref: number, over: Partial<Descriptor> = {}): Descriptor {
  return {
    field_ref,
    tag: 'input',
    type: 'text',
    name: '',
    id: '',
    autocomplete: '',
    aria_label: '',
    placeholder: '',
    label: '',
    data_automation_id: '',
    required: false,
    ...over,
  }
}
function mp(field_ref: number, canonical: Canonical, confidence = 0.95): Mapping {
  return { field_ref, canonical, confidence, source: 'heuristic' }
}
function plan(ds: Descriptor[], ms: Mapping[], hasResume = false) {
  return planFill(ds, new Map(ms.map((m) => [m.field_ref, m])), profile, hasResume)
}

describe('planFill (fill decisions — the trust boundary)', () => {
  test('derives first/last name from the single profile name', () => {
    const p = plan([d(0), d(1)], [mp(0, 'first_name'), mp(1, 'last_name')])
    expect(p[0]).toMatchObject({ action: 'fill', value: 'Ada' })
    expect(p[1]).toMatchObject({ action: 'fill', value: 'Lovelace' })
  })

  test('fills links, location, and work authorization from profile', () => {
    const p = plan(
      [d(0), d(1), d(2), d(3)],
      [mp(0, 'linkedin'), mp(1, 'location'), mp(2, 'work_authorization'), mp(3, 'portfolio')],
    )
    expect(p.map((x) => x.value)).toEqual([
      'https://linkedin.com/in/ada',
      'London, UK',
      'Authorized to work in the UK',
      'https://ada.dev',
    ])
  })

  test('a mapped field with no profile value is left BLANK, never guessed', () => {
    const p = plan([d(0, { label: 'Years of experience' })], [mp(0, 'years_experience')])
    expect(p[0].action).toBe('blank')
    expect(p[0].value).toBeUndefined()
  })

  test('low-confidence mapping is left blank AND flagged', () => {
    const p = plan([d(0, { label: 'Ambiguous' })], [mp(0, 'email', 0.4)])
    expect(p[0].action).toBe('flag')
  })

  test('free_text questions route to the answerer; cover_letter stays with the user (T13)', () => {
    expect(plan([d(0, { tag: 'textarea', label: 'Why here?' })], [mp(0, 'free_text', 0.6)])[0].action).toBe('answer')
    expect(plan([d(0, { type: 'file', label: 'Cover letter' })], [mp(0, 'cover_letter')])[0].action).toBe('flag')
  })

  test('resume_upload attaches when a résumé exists, else blank', () => {
    const ds = [d(0, { type: 'file', label: 'Resume' })]
    expect(plan(ds, [mp(0, 'resume_upload')], true)[0].action).toBe('attach')
    expect(plan(ds, [mp(0, 'resume_upload')], false)[0].action).toBe('blank')
  })

  test('unknown non-required fields are skipped; unknown required is flagged', () => {
    const p = plan(
      [d(0, { required: false }), d(1, { required: true })],
      [mp(0, 'unknown', 0.2), mp(1, 'unknown', 0.2)],
    )
    expect(p.find((x) => x.field_ref === 0)).toBeUndefined()
    expect(p.find((x) => x.field_ref === 1)!.action).toBe('flag')
  })
})
