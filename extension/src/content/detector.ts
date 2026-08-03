import type { Descriptor } from '../shared/types'
import { clean, labelByFor } from './dom'

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
        context: contextFor(el),
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

const HEADING = 'h1, h2, h3, h4, h5, h6, [role="heading"]'

/** Structure-only nearby signal for the LLM mapping lane (T19): the enclosing
 *  fieldset legend + the nearest section heading above the field. Drawn ONLY
 *  from heading/legend elements — never from inputs or their values — so no
 *  entered value can cross the privacy boundary. Capped so the payload stays small. */
function contextFor(el: HTMLElement): string {
  const parts: string[] = []
  const legend = el.closest('fieldset')?.querySelector('legend')?.textContent
  if (legend?.trim()) parts.push(clean(legend))
  const heading = nearestHeading(el)
  if (heading && !parts.includes(heading)) parts.push(heading)
  return parts.join(' · ').slice(0, 200)
}

/** The nearest section heading preceding the field: scan previous siblings up
 *  the ancestor chain, heading elements only (structural, never a value). */
function nearestHeading(el: Element): string {
  for (let node: Element | null = el; node && node !== document.body; node = node.parentElement) {
    for (let sib = node.previousElementSibling; sib; sib = sib.previousElementSibling) {
      if (sib.matches(HEADING) && sib.textContent?.trim()) return clean(sib.textContent)
    }
  }
  return ''
}

/** Resolve the human label for a field, trying the reliable signals first. */
function labelFor(el: HTMLElement): string {
  const forLabel = labelByFor(el)
  if (forLabel) return forLabel
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
