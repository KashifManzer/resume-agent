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
