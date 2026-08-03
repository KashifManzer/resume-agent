import { describe, expect, test } from 'vitest'

import { alreadyFilled, fitMaxLength, setNativeValue } from '../src/content/apply'

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
