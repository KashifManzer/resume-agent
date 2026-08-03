import type { PlanItem } from '../shared/types'
import type { DetectedField } from './detector'

type Valued = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement

/** Set a field's value the way a real keystroke would, so React/Vue-controlled
 *  ATS forms register it: write through the native setter (bypassing the
 *  framework's value shim), then dispatch bubbling input + change events. */
export function setNativeValue(el: Valued, value: string): void {
  const proto =
    el instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : el instanceof HTMLSelectElement
        ? HTMLSelectElement.prototype
        : HTMLInputElement.prototype
  const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set
  const previous = el.value
  if (setter) setter.call(el, value)
  else el.value = value
  // React caches the last value in a hidden `_valueTracker`. If that cache still
  // equals our new value, React treats the write as a no-op and never fires
  // onChange — so a later re-render (e.g. Ashby's "autofill from résumé" re-parse)
  // reverts our text. Rewind the tracker to the previous value so React sees a
  // real change and commits it to state. (jsdom/no-React → tracker undefined, skip.)
  const tracker = (el as unknown as { _valueTracker?: { setValue(v: string): void } })._valueTracker
  if (tracker) tracker.setValue(previous)
  el.dispatchEvent(new Event('input', { bubbles: true }))
  el.dispatchEvent(new Event('change', { bubbles: true }))
}

/** Normalize option/label text for tolerant matching: lowercase, punctuation →
 *  space, collapse whitespace. So "United States" matches "United States of
 *  America". */
function norm(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()
}

/** Pick the candidate matching `value`: exact normalized match on its text (or
 *  optional alt text like an <option> value) wins; else the UNIQUE candidate
 *  whose text CONTAINS the value. Returns null on no match OR ambiguity — never
 *  guess a wrong option on a submitted application. Shared by <select> +
 *  combobox (T19). */
export function pickOption<T>(items: T[], value: string, textOf: (t: T) => string, altOf?: (t: T) => string): T | null {
  const want = norm(value)
  if (!want) return null
  const exact = items.find((it) => norm(textOf(it)) === want || (altOf ? norm(altOf(it)) === want : false))
  if (exact) return exact
  const contains = items.filter((it) => norm(textOf(it)).includes(want))
  return contains.length === 1 ? contains[0] : null
}

/** Select the <option> matching `value`. Returns false (leaves the select
 *  untouched) on no match/ambiguity, so the caller flags it — never a wrong pick. */
export function setSelectValue(el: HTMLSelectElement, value: string): boolean {
  // skip the empty / "Select One" placeholder option — it is never an answer.
  const opts = [...el.options].filter((o) => o.value !== '' && norm(o.text) !== 'select one')
  const match = pickOption(opts, value, (o) => o.text, (o) => o.value)
  if (!match) return false
  setNativeValue(el, match.value)
  return true
}

/** Select one radio option the way a real click would (T17). Native `checked`
 *  setter (bypass the framework shim) + a bubbling click/change so React/Vue
 *  radio groups register the choice. Radios never toggle off, so this is safe. */
export function selectRadio(el: HTMLInputElement): void {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'checked')?.set
  if (setter) setter.call(el, true)
  else el.checked = true
  el.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  el.dispatchEvent(new Event('input', { bubbles: true }))
  el.dispatchEvent(new Event('change', { bubbles: true }))
}

/** True when the user already picked an option in this group — never overwrite it. */
export function anyChecked(els: HTMLInputElement[]): boolean {
  return els.some((el) => el.checked)
}

/** Attach a File to an <input type=file> via DataTransfer (the only way to set
 *  .files programmatically), then fire change so the form picks it up. */
export function attachFile(input: HTMLInputElement, file: File): void {
  const dt = new DataTransfer()
  dt.items.add(file)
  input.files = dt.files
  input.dispatchEvent(new Event('input', { bubbles: true }))
  input.dispatchEvent(new Event('change', { bubbles: true }))
}

/** True when the user already answered — we never overwrite their input. Also
 *  makes re-Fill idempotent: our own prior answer counts as "already there". */
export function alreadyFilled(el: Valued): boolean {
  return el.value.trim().length > 0
}

/** Clamp to the field's maxlength so an AI draft can never exceed a hard cap.
 *  ponytail: honors the maxlength attribute only; fuzzy "max N words" hints in
 *  label prose are deferred until a real form needs them. */
export function fitMaxLength(el: HTMLInputElement | HTMLTextAreaElement, text: string): string {
  const max = el.maxLength
  return max > 0 && text.length > max ? text.slice(0, max) : text
}

/** True for an ARIA combobox trigger (Workday Country/State/Phone-type): an
 *  element that opens a listbox popup. Its options live outside it, so it needs
 *  the async open→type→pick flow below, not a plain value write. */
export function isCombobox(el: Element): boolean {
  return el.matches('[role="combobox"], [aria-haspopup="listbox"]')
}

/** Poll `get` until it returns truthy or the timeout elapses — the popup listbox
 *  renders a beat after the trigger opens, and re-filters a beat after typing.
 *  Small and dependency-free. */
async function waitFor<T>(get: () => T | null, timeoutMs = 2000, stepMs = 50): Promise<T | null> {
  const deadline = Date.now() + timeoutMs
  for (;;) {
    const v = get()
    if (v) return v
    if (Date.now() >= deadline) return null
    await new Promise((r) => setTimeout(r, stepMs))
  }
}

/** Drive an ARIA combobox to `value` (T19, the Workday lane): open the popup,
 *  type into its search box if present (typeahead), wait for the listbox, then
 *  click the option whose text exactly/uniquely matches. Returns false — closing
 *  the popup, leaving the field untouched — on no match or ambiguity; NEVER a
 *  blind first-row pick. Timing/DOM varies per ATS, so this is the piece that
 *  MUST be live-verified. */
export async function fillCombobox(trigger: HTMLElement, value: string): Promise<boolean> {
  // Interact via dispatched pointer EVENTS (never the direct click method — the
  // no-submit guard forbids it). NOTE: this is an educated-guess hardening from a
  // live Workday run where the dropdown OPENED but never selected. Two likely
  // causes addressed: (1) the option list is VIRTUALIZED — only visible rows are
  // in the DOM — so we type into the search to filter our match into existence;
  // (2) rows select on the full mouse sequence, not a lone click. LIVE-VERIFY on
  // a real Workday form is still required to confirm.
  const mouse = (el: Element, ...types: string[]): void => {
    for (const t of types) el.dispatchEvent(new MouseEvent(t, { bubbles: true }))
  }
  const close = (): void => {
    trigger.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  }

  mouse(trigger, 'mousedown', 'mouseup', 'click') // open the listbox popup
  const listbox = await waitFor(() => document.querySelector('[role="listbox"]'))
  if (!listbox) return false

  // Typeahead: type the value into the popup search so a virtualized list filters
  // down until our match actually renders into the DOM.
  const search = (listbox.querySelector('input') ??
    document.querySelector('[role="listbox"] input, [role="combobox"] input')) as HTMLInputElement | null
  if (search) {
    search.focus()
    setNativeValue(search, value)
    search.dispatchEvent(new KeyboardEvent('keyup', { key: value.slice(-1) || 'a', bubbles: true }))
  }

  // Wait for the exact/unique MATCH to be present (post-filter) — not just any option.
  const match = await waitFor(() => {
    const opts = [...document.querySelectorAll<HTMLElement>('[role="option"]')].filter(
      (o) => (o.textContent ?? '').trim() && norm(o.textContent ?? '') !== 'select one',
    )
    return opts.length ? pickOption(opts, value, (o) => o.textContent ?? '') : null
  })
  if (!match) {
    close() // no confident match → leave the field untouched, never a wrong/first-row pick
    return false
  }

  match.scrollIntoView?.({ block: 'nearest' }) // a virtualized row must be in view to receive events
  mouse(match, 'mousedown', 'mouseup', 'click') // select on the full pointer sequence, not click alone
  return true
}

/** Execute a fill plan against the detected elements. 'blank'/'flag' items are
 *  deliberately left untouched — we never write a value we're unsure of.
 *  Comboboxes are skipped here — the async pass (fillComboboxes) handles them. */
export function applyPlan(fields: DetectedField[], plan: PlanItem[], resume: File | null): void {
  const byRef = new Map(fields.map((f) => [f.descriptor.field_ref, f.el]))
  for (const item of plan) {
    const el = byRef.get(item.field_ref)
    if (!el) continue
    if (item.action === 'fill' && item.value != null) {
      if (isCombobox(el)) continue // async combobox pass owns these
      if (el instanceof HTMLSelectElement) {
        // A dropdown needs option-matching, not a raw value write (P2). No option
        // matched → downgrade to blank + flag; never leave a wrong selection.
        if (!setSelectValue(el, item.value)) {
          item.action = 'blank'
          item.value = undefined
          item.reason = "couldn't match a dropdown option — pick it yourself"
        }
      } else {
        setNativeValue(el as Valued, item.value)
      }
    } else if (item.action === 'attach' && resume) attachFile(el as HTMLInputElement, resume)
  }
}

/** Async fill pass for ARIA comboboxes (T19). Runs after applyPlan; mutates each
 *  combobox 'fill' item to blank + flag when the option can't be matched, so an
 *  unmatched combobox is never left in a wrong state. */
export async function fillComboboxes(fields: DetectedField[], plan: PlanItem[]): Promise<void> {
  const byRef = new Map(fields.map((f) => [f.descriptor.field_ref, f.el]))
  for (const item of plan) {
    if (item.action !== 'fill' || item.value == null) continue
    const el = byRef.get(item.field_ref)
    if (!el || !isCombobox(el)) continue
    if (!(await fillCombobox(el as HTMLElement, item.value))) {
      item.action = 'blank'
      item.value = undefined
      item.reason = "couldn't match a dropdown option — pick it yourself"
    }
  }
}
