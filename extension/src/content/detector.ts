import type { Descriptor } from '../shared/types'

export interface DetectedField {
  el: HTMLElement
  descriptor: Descriptor
}

const FILLABLE = 'input, select, textarea'
// input types that are never profile-fillable text/file fields. 'radio' is
// excluded here because radio *groups* are detected separately (T17 choices.ts)
// as one logical Yes/No/choice question, not one field per option.
const SKIP_TYPES = new Set(['submit', 'button', 'reset', 'hidden', 'image', 'radio'])

/** Read every fillable field on the page into a structure-only Descriptor.
 *  Pure DOM read — no chrome APIs — so it unit-tests in jsdom over fixtures. */
export function detectFields(root: Document | Element = document): DetectedField[] {
  const out: DetectedField[] = []
  for (const el of root.querySelectorAll<HTMLElement>(FILLABLE)) {
    const tag = el.tagName.toLowerCase()
    const type = (el.getAttribute('type') || (tag === 'input' ? 'text' : tag)).toLowerCase()
    if (tag === 'input' && SKIP_TYPES.has(type)) continue
    // Never touch a CAPTCHA response field (e.g. Ashby's hidden g-recaptcha-response).
    if (/captcha/i.test(`${el.getAttribute('name') || ''} ${el.id}`)) continue
    if (isHoneypot(el)) continue // bot-trap fields: writing them flags us as a bot
    if (!isVisible(el)) continue
    out.push({
      el,
      descriptor: {
        field_ref: out.length,
        tag,
        type,
        name: el.getAttribute('name') || '',
        id: el.id || '',
        autocomplete: el.getAttribute('autocomplete') || '',
        aria_label: el.getAttribute('aria-label') || '',
        placeholder: el.getAttribute('placeholder') || '',
        label: labelFor(el),
        data_automation_id: el.getAttribute('data-automation-id') || '',
        required: el.hasAttribute('required') || el.getAttribute('aria-required') === 'true',
      },
    })
  }
  return out
}

function isVisible(el: HTMLElement): boolean {
  if (el.hidden) return false
  const cs = el.ownerDocument.defaultView?.getComputedStyle(el)
  if (!cs) return true
  if (cs.display === 'none' || cs.visibility === 'hidden') return false
  // opacity:0 hides a field the way honeypots do — BUT it's also the normal
  // pattern for a résumé <input type=file> sitting invisibly under a styled
  // "Attach résumé" button (Lever, Greenhouse). Only reject opacity:0 for
  // non-file fields; the honeypot guard (name/aria) still covers file traps.
  const isFile = el.tagName === 'INPUT' && (el.getAttribute('type') || '').toLowerCase() === 'file'
  if (cs.opacity === '0' && !isFile) return false
  return true
}

// Honeypots are decoy fields hidden from humans; only bots fill them. Skip the
// common tells: a name/id/class trap word, or an aria-hidden wrapper. (display/
// visibility/opacity hiding is caught by isVisible.)
const HONEYPOT = /honeypot|bot[-_]?field|hp[-_]?field|confirm[-_]?email/i
function isHoneypot(el: HTMLElement): boolean {
  const sig = `${el.getAttribute('name') || ''} ${el.id} ${el.className}`
  if (HONEYPOT.test(sig)) return true
  return el.closest('[aria-hidden="true"]') !== null
}

/** Resolve the human label for a field, trying the reliable signals first. */
function labelFor(el: HTMLElement): string {
  if (el.id) {
    const l = el.ownerDocument.querySelector(`label[for="${el.id.replace(/["\\]/g, '\\$&')}"]`)
    if (l?.textContent) return clean(l.textContent)
  }
  const wrap = el.closest('label')
  if (wrap?.textContent) return clean(wrap.textContent)

  const ref = el.getAttribute('aria-labelledby')
  if (ref) {
    const text = clean(
      ref
        .split(/\s+/)
        .map((id) => el.ownerDocument.getElementById(id)?.textContent || '')
        .join(' '),
    )
    if (text) return text
  }
  const aria = el.getAttribute('aria-label')
  if (aria) return clean(aria)

  const container = el.closest('.field, .application-field, .application-question, li, fieldset, div, p')
  const label = container?.querySelector('label')
  if (label?.textContent) return clean(label.textContent)

  return clean(el.getAttribute('placeholder') || '')
}

function clean(s: string): string {
  return s.replace(/[*✱]/g, ' ').replace(/\s+/g, ' ').trim()
}
