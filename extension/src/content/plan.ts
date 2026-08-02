import { FILL_THRESHOLD } from '../shared/config'
import type { Canonical, Descriptor, Mapping, PlanItem, Profile } from '../shared/types'

/** The value that goes in a canonical field — ALWAYS from the profile, never
 *  invented. Returns null when the profile has nothing (→ leave blank). */
function valueFor(c: Canonical, p: Profile): string | null {
  const parts = (p.name || '').trim().split(/\s+/).filter(Boolean)
  switch (c) {
    case 'full_name':
      return p.name?.trim() || null
    case 'first_name':
      return parts[0] || null
    case 'last_name':
      return parts.length > 1 ? parts.slice(1).join(' ') : null
    case 'email':
      return p.email || null
    case 'phone':
      return p.phone || null
    case 'location':
      return p.location || null
    case 'work_authorization':
      return p.work_auth || null
    case 'linkedin':
      return p.links?.linkedin || null
    case 'github':
      return p.links?.github || null
    case 'portfolio':
    case 'website':
      return p.links?.portfolio || null
    default:
      return null // years_experience, cover_letter, free_text, unknown, resume_upload
  }
}

/** Decide, per field, what to do — the trust boundary. The mapper says what a
 *  field *means*; this decides whether we have a value and dare to write it. */
export function planFill(
  ds: Descriptor[],
  mappings: Map<number, Mapping>,
  profile: Profile,
  hasResume: boolean,
  opts: { threshold?: number } = {},
): PlanItem[] {
  const threshold = opts.threshold ?? FILL_THRESHOLD
  const out: PlanItem[] = []
  for (const d of ds) {
    const m = mappings.get(d.field_ref)
    const canonical: Canonical = m?.canonical ?? 'unknown'
    const confidence = m?.confidence ?? 0
    const base = { field_ref: d.field_ref, label: d.label || d.name || d.id || '(field)', canonical }

    if (canonical === 'resume_upload') {
      out.push({ ...base, action: hasResume ? 'attach' : 'blank', reason: hasResume ? undefined : 'no tailored résumé selected' })
      continue
    }
    // free-text screening question → answered by the backend answerer (T13).
    if (canonical === 'free_text') {
      out.push({ ...base, action: 'answer' })
      continue
    }
    // cover letter is a separate, bigger ticket — leave it to the user.
    if (canonical === 'cover_letter') {
      out.push({ ...base, action: 'flag', reason: 'answer this yourself' })
      continue
    }
    if (canonical === 'unknown') {
      // skip quietly unless required — then surface it so nothing is missed
      if (d.required) out.push({ ...base, action: 'flag', reason: 'not recognized — fill yourself' })
      continue
    }
    if (confidence < threshold) {
      out.push({ ...base, action: 'flag', reason: 'unsure what this field wants' })
      continue
    }
    const value = valueFor(canonical, profile)
    if (value == null) out.push({ ...base, action: 'blank', reason: 'no saved value in your profile' })
    else out.push({ ...base, action: 'fill', value })
  }
  return out
}
