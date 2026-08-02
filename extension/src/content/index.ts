// Content script (T12). Runs in the ATS page, in the user's own session. It
// detects the form, fills factual fields, and attaches the tailored résumé —
// then stops. There is NO code path here that clicks a submit control.
import { sendToBackground } from '../shared/messaging'
import type { AnswerResult, FillResult, Mapping, PdfPayload, PlanItem, Profile } from '../shared/types'
import { alreadyFilled, anyChecked, applyPlan, fitMaxLength, selectRadio, setNativeValue } from './apply'
import { decideChoice } from './choice-answer'
import { detectRadioGroups } from './choices'
import type { DetectedField } from './detector'
import { detectFields } from './detector'
import { mapAll } from './mapper'
import { planFill } from './plan'
import { focusField, renderProofMarks } from './proofmarks'

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === 'PING') {
    sendResponse({ ok: true })
    return
  }
  // DETECT (T15): lets the popup show the "not on an application page" state
  // proactively — a pure count, no values leave the page.
  if (msg?.type === 'DETECT') {
    const n = detectFields(document).length
    sendResponse({ formPresent: n > 0, fieldCount: n })
    return
  }
  // FOCUS_FIELD (T15): jump-to-field from the popup's review list.
  if (msg?.type === 'FOCUS_FIELD') {
    focusField(msg.field_ref as number)
    sendResponse({ ok: true })
    return
  }
  if (msg?.type === 'FILL') {
    fill(msg.jobId as string | null)
      .then(sendResponse)
      .catch((e) => sendResponse(empty(String(e?.message ?? e))))
    return true // keep the message channel open for the async response
  }
})

async function fill(jobId: string | null): Promise<FillResult> {
  const fields = detectFields(document)
  if (fields.length === 0) return empty('No application form detected on this page.')

  const descriptors = fields.map((f) => f.descriptor)
  const profile = await sendToBackground<Profile>({ type: 'GET_PROFILE' })

  // Fast lane: deterministic mapping resolves the stable ~80% in-browser, free.
  const mappings = new Map(mapAll(descriptors).map((m) => [m.field_ref, m]))
  // LLM lane: ask the backend to resolve only what we couldn't — sending field
  // STRUCTURE ONLY (no values, no page HTML). Failures leave them unknown.
  const unresolved = descriptors.filter((d) => mappings.get(d.field_ref)?.canonical === 'unknown')
  if (unresolved.length) {
    try {
      const { mappings: resolved } = await sendToBackground<{ mappings: Mapping[] }>({
        type: 'MAP_FIELDS',
        host: location.host,
        fields: unresolved,
      })
      for (const m of resolved) mappings.set(m.field_ref, m)
    } catch {
      // backend unreachable → those fields stay unknown; planFill leaves them for the user
    }
  }

  const resume = jobId ? await getResume(jobId) : null

  const plan = planFill(descriptors, mappings, profile, resume != null)
  applyPlan(fields, plan, resume)
  await answerFreeText(fields, plan, jobId)

  // T17: radio-group screening questions (work-auth, EEO, legal attestations) —
  // pre-select from the user's profile / honest defaults, always flagged for review.
  const choice = fillChoices(fields.length, profile)

  const allFields = [...fields, ...choice.fields]
  const allPlan = [...plan, ...choice.plan]
  renderProofMarks(allFields, allPlan) // T15: mark the page like a proofread manuscript
  reassertFills(allFields, allPlan) // Ashby et al. re-render on résumé parse — re-apply after it settles
  return group(allPlan)
}

/** The live element for a field descriptor — re-queried by id/name so a form
 *  that swapped the DOM node out (an ATS re-render) is still reachable. */
function liveElement(f: DetectedField): HTMLInputElement | HTMLTextAreaElement | null {
  const d = f.descriptor
  const byId = d.id && document.getElementById(d.id)
  if (byId) return byId as HTMLInputElement
  if (d.name) {
    const byName = document.querySelector(`[name="${CSS.escape(d.name)}"]`)
    if (byName) return byName as HTMLInputElement
  }
  return f.el.isConnected ? (f.el as HTMLInputElement) : null
}

/** Some ATSes (Ashby's "autofill from résumé") parse the attached PDF and
 *  re-render the form a beat later, blanking values we wrote. Principle: be the
 *  last writer. Rather than guess a delay, watch the form settle and re-apply our
 *  fills on each mutation batch — ONLY where the field is now empty, so we never
 *  overwrite the user or the ATS's own parsed value (idempotent, no thrash). */
function reassertFills(fields: DetectedField[], plan: PlanItem[]): void {
  const byRef = new Map(fields.map((f) => [f.descriptor.field_ref, f]))
  const redo = () => {
    for (const item of plan) {
      if (item.action !== 'fill' || item.value == null || item.control === 'choice') continue
      const f = byRef.get(item.field_ref)
      const el = f && liveElement(f)
      if (el && el.value.trim() === '') setNativeValue(el, item.value)
    }
  }
  let timer = 0
  const obs = new MutationObserver(() => {
    clearTimeout(timer)
    timer = window.setTimeout(redo, 250) // debounce bursts into one re-apply
  })
  obs.observe(document.body, { childList: true, subtree: true })
  redo() // once now, in case the form never re-renders
  setTimeout(() => obs.disconnect(), 8000) // bounded: stop once it has surely settled
}

/** Answer Yes/No/choice radio groups deterministically (T17). Anchors each
 *  group's proof mark on its question block. Only records a mark when we filled
 *  it or it's a required question we couldn't answer — never per-option noise. */
function fillChoices(startRef: number, profile: Profile): { fields: DetectedField[]; plan: PlanItem[] } {
  const fields: DetectedField[] = []
  const plan: PlanItem[] = []
  for (const g of detectRadioGroups(document, startRef)) {
    const base = { field_ref: g.field_ref, label: g.question || g.name, canonical: 'free_text' as const }
    let item: PlanItem | null = null
    if (anyChecked(g.options.map((o) => o.el))) {
      item = { ...base, action: 'flag', reason: 'you already answered this' }
    } else {
      const d = decideChoice(g, profile)
      if (d.option) {
        selectRadio(d.option.el)
        item = { ...base, action: 'fill', value: d.option.label, needsReview: d.needsReview, reason: d.reason, control: 'choice' }
      } else if (g.required) {
        item = { ...base, action: 'blank', reason: d.reason ?? 'answer this yourself' }
      }
    }
    if (!item) continue // leave non-required, unanswerable groups unmarked (no clutter)
    fields.push({
      el: g.container,
      descriptor: {
        field_ref: g.field_ref, tag: 'fieldset', type: 'radio', name: g.name, id: '',
        autocomplete: '', aria_label: '', placeholder: '', label: g.question,
        data_automation_id: '', required: g.required,
      },
    })
    plan.push(item)
  }
  return { fields, plan }
}

/** Fill each free-text screening question via the backend answerer (T13). Each
 *  item is mutated in place: → 'fill' (with an AI-draft badge), 'blank', or
 *  'flag'. Guards: never overwrite the user's own input, respect maxlength,
 *  and stay idempotent (a re-Fill sees our prior answer and skips). */
async function answerFreeText(fields: DetectedField[], plan: PlanItem[], jobId: string | null): Promise<void> {
  const byRef = new Map(fields.map((f) => [f.descriptor.field_ref, f.el]))
  for (const item of plan) {
    if (item.action !== 'answer') continue
    const el = byRef.get(item.field_ref) as HTMLInputElement | HTMLTextAreaElement | undefined
    if (!el) {
      item.action = 'flag'
      continue
    }
    if (alreadyFilled(el)) {
      item.action = 'flag'
      item.reason = 'you already answered this'
      continue
    }
    let res: AnswerResult
    try {
      res = await sendToBackground<AnswerResult>({
        type: 'ANSWER',
        question: item.label,
        jobId,
        host: location.host,
      })
    } catch {
      item.action = 'flag'
      item.reason = "couldn't reach the answerer — answer this yourself"
      continue
    }
    if (!res.answer) {
      // A free-text question we TRIED but couldn't answer is a blank the user
      // must fill — show it as a visible "needs you" caret, not a generic flag
      // (those are now collapsed to a popup count). Never-auto / high-stakes ones
      // stay a flag so they surface as the distinct "sensitive" mark.
      const sensitive = /high-stakes|leave this to yourself|sensitive/i.test(item.reason ?? res.reason ?? '')
      item.action = sensitive ? 'flag' : 'blank'
      item.reason = res.reason ?? 'answer this yourself'
      continue
    }
    const value = fitMaxLength(el, res.answer)
    setNativeValue(el, value)
    item.action = 'fill'
    item.value = value
    item.needsReview = res.needs_review
    item.source = res.source
  }
}

async function getResume(jobId: string): Promise<File | null> {
  try {
    const { base64, filename } = await sendToBackground<PdfPayload>({ type: 'GET_PDF', jobId })
    const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0))
    return new File([bytes], filename, { type: 'application/pdf' })
  } catch {
    return null
  }
}

function group(plan: PlanItem[]): FillResult {
  return {
    filled: plan.filter((p) => p.action === 'fill'),
    attached: plan.filter((p) => p.action === 'attach'),
    blank: plan.filter((p) => p.action === 'blank'),
    flagged: plan.filter((p) => p.action === 'flag'),
  }
}

function empty(error: string): FillResult {
  return { filled: [], attached: [], blank: [], flagged: [], error }
}
