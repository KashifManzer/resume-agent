import { describe, expect, test } from 'vitest'

import { alreadyFilled, applyPlan, fillCombobox, fitMaxLength, pickOption, setNativeValue, setSelectValue } from '../src/content/apply'
import type { DetectedField } from '../src/content/detector'
import type { PlanItem } from '../src/shared/types'
import { bare } from './util'

describe('setNativeValue (React-controlled inputs need dispatched events)', () => {
  test('sets the value and dispatches input then change, bubbling', () => {
    document.body.innerHTML = '<input id="x" />'
    const el = document.getElementById('x') as HTMLInputElement
    const seen: string[] = []
    el.addEventListener('input', (e) => seen.push(`input:${e.bubbles}`))
    el.addEventListener('change', (e) => seen.push(`change:${e.bubbles}`))
    setNativeValue(el, 'ada@analytical.io')
    expect(el.value).toBe('ada@analytical.io')
    expect(seen).toEqual(['input:true', 'change:true'])
  })

  test('works on a textarea', () => {
    document.body.innerHTML = '<textarea id="t"></textarea>'
    const el = document.getElementById('t') as HTMLTextAreaElement
    setNativeValue(el, 'line one\nline two')
    expect(el.value).toBe('line one\nline two')
  })

  test('drives a <select> — the generic write path covers dropdowns (T19)', () => {
    document.body.innerHTML =
      '<select id="s"><option value="">—</option><option value="us">United States</option></select>'
    const el = document.getElementById('s') as HTMLSelectElement
    const seen: string[] = []
    el.addEventListener('change', (e) => seen.push(`change:${e.bubbles}`))
    setNativeValue(el, 'us') // matching an <option> value is P2's job; the write path is generic now
    expect(el.value).toBe('us')
    expect(el.selectedIndex).toBe(1)
    expect(seen).toEqual(['change:true'])
  })
})

describe('setSelectValue (P2: dropdown option matching)', () => {
  const sel = (html: string): HTMLSelectElement => {
    document.body.innerHTML = `<select id="s">${html}</select>`
    return document.getElementById('s') as HTMLSelectElement
  }

  test('exact normalized match sets the option and fires change', () => {
    const el = sel('<option value="">Select One</option><option value="us">United States of America</option><option value="ca">Canada</option>')
    const seen: string[] = []
    el.addEventListener('change', () => seen.push('change'))
    expect(setSelectValue(el, 'united states of america')).toBe(true)
    expect(el.value).toBe('us')
    expect(seen).toEqual(['change'])
  })

  test('unique contains-match wins ("United States" → "United States of America")', () => {
    const el = sel('<option value="">Select One</option><option value="us">United States of America</option><option value="ca">Canada</option>')
    expect(setSelectValue(el, 'United States')).toBe(true)
    expect(el.value).toBe('us')
  })

  test('matches by option value too (an exact code like "US")', () => {
    const el = sel('<option value="">-</option><option value="US">United States of America</option>')
    expect(setSelectValue(el, 'US')).toBe(true)
    expect(el.value).toBe('US')
  })

  test('no match leaves the placeholder selected and returns false', () => {
    const el = sel('<option value="">Select One</option><option value="fr">France</option>')
    expect(setSelectValue(el, 'Germany')).toBe(false)
    expect(el.value).toBe('') // never a wrong pick
  })

  test('ambiguous (multiple contains, no exact) → false, no guess', () => {
    const el = sel('<option value="">-</option><option value="n">New York</option><option value="y">York County</option>')
    expect(setSelectValue(el, 'York')).toBe(false)
  })

  test('never selects the empty / "Select One" placeholder', () => {
    const el = sel('<option value="">Select One</option><option value="y">Yes</option>')
    expect(setSelectValue(el, 'select one')).toBe(false)
  })
})

describe('applyPlan across widgets (P2)', () => {
  test('fills a matching <select>, downgrades an unmatched one to blank (never a wrong pick)', () => {
    document.body.innerHTML =
      '<select id="s1"><option value="">-</option><option value="ca">Canada</option></select>' +
      '<select id="s2"><option value="">-</option><option value="fr">France</option></select>'
    const s1 = document.getElementById('s1') as HTMLSelectElement
    const s2 = document.getElementById('s2') as HTMLSelectElement
    const fields: DetectedField[] = [
      { el: s1, descriptor: bare({ field_ref: 0, tag: 'select' }) },
      { el: s2, descriptor: bare({ field_ref: 1, tag: 'select' }) },
    ]
    const plan: PlanItem[] = [
      { field_ref: 0, label: 'Country', canonical: 'location', action: 'fill', value: 'Canada' },
      { field_ref: 1, label: 'Country', canonical: 'location', action: 'fill', value: 'Germany' },
    ]
    applyPlan(fields, plan, null)
    expect(s1.value).toBe('ca') // matched
    expect(plan[1].action).toBe('blank') // unmatched → downgraded
    expect(s2.value).toBe('') // untouched, no wrong selection
  })
})

describe('pickOption (P2: the shared option matcher)', () => {
  const items = ['Canada', 'United States of America', 'United Kingdom']
  const id = (x: string) => x

  test('exact normalized match wins', () => {
    expect(pickOption(items, 'canada', id)).toBe('Canada')
  })
  test('unique contains-match wins', () => {
    expect(pickOption(items, 'United States', id)).toBe('United States of America')
  })
  test('ambiguous (multiple contain, no exact) → null', () => {
    expect(pickOption(items, 'United', id)).toBe(null) // both "United ..." contain it
  })
  test('no match → null', () => {
    expect(pickOption(items, 'France', id)).toBe(null)
  })
})

describe('fillCombobox (P2: the Workday ARIA-combobox driver)', () => {
  // jsdom can't run Workday's listbox JS, so we simulate the popup: clicking the
  // trigger appends a [role=listbox] with a search input + [role=option] rows.
  const withPopup = (triggerHtml: string, optionsHtml: string) => {
    document.body.innerHTML = triggerHtml
    const btn = document.body.firstElementChild as HTMLElement
    btn.addEventListener('click', () => {
      if (document.querySelector('[role=listbox]')) return
      const lb = document.createElement('div')
      lb.setAttribute('role', 'listbox')
      lb.innerHTML = `<input aria-label="Search" />${optionsHtml}`
      document.body.appendChild(lb)
    })
    return btn
  }

  test('opens, matches an option by text, and clicks it', async () => {
    const btn = withPopup(
      '<button aria-haspopup="listbox">Select One</button>',
      '<div role="option">Canada</div><div role="option">United States of America</div>',
    )
    let picked = ''
    document.addEventListener('click', (e) => {
      const t = e.target as HTMLElement
      if (t.getAttribute?.('role') === 'option') picked = t.textContent ?? ''
    })
    expect(await fillCombobox(btn, 'United States')).toBe(true)
    expect(picked).toBe('United States of America') // exact/unique match, never a blind first row
  })

  test('no match → false, nothing picked (never a blind first-row pick)', async () => {
    const btn = withPopup(
      '<button aria-haspopup="listbox">-</button>',
      '<div role="option">Canada</div><div role="option">Mexico</div>',
    )
    let picked = ''
    document.addEventListener('click', (e) => {
      const t = e.target as HTMLElement
      if (t.getAttribute?.('role') === 'option') picked = t.textContent ?? ''
    })
    expect(await fillCombobox(btn, 'Germany')).toBe(false)
    expect(picked).toBe('')
  })
})

describe('free-text answer guards (T13)', () => {
  test('alreadyFilled: never overwrite the user (and makes re-Fill idempotent)', () => {
    document.body.innerHTML = '<textarea id="a"></textarea><textarea id="b">mine</textarea>'
    expect(alreadyFilled(document.getElementById('a') as HTMLTextAreaElement)).toBe(false)
    expect(alreadyFilled(document.getElementById('b') as HTMLTextAreaElement)).toBe(true)
  })

  test('fitMaxLength: clamps to the field maxlength, passes through otherwise', () => {
    document.body.innerHTML = '<textarea id="t" maxlength="5"></textarea><textarea id="u"></textarea>'
    const capped = document.getElementById('t') as HTMLTextAreaElement
    const free = document.getElementById('u') as HTMLTextAreaElement
    expect(fitMaxLength(capped, 'abcdefgh')).toBe('abcde')
    expect(fitMaxLength(free, 'abcdefgh')).toBe('abcdefgh')
  })
})
