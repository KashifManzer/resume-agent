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

/** Execute a fill plan against the detected elements. 'blank'/'flag' items are
 *  deliberately left untouched — we never write a value we're unsure of. */
export function applyPlan(fields: DetectedField[], plan: PlanItem[], resume: File | null): void {
  const byRef = new Map(fields.map((f) => [f.descriptor.field_ref, f.el]))
  for (const item of plan) {
    const el = byRef.get(item.field_ref)
    if (!el) continue
    if (item.action === 'fill' && item.value != null) setNativeValue(el as Valued, item.value)
    else if (item.action === 'attach' && resume) attachFile(el as HTMLInputElement, resume)
  }
}
