import { useState } from 'react'
import { Link } from 'react-router-dom'

import { Sheet } from '@/components/ui/Sheet'
import { useSetupProgress } from '@/hooks/useSetup'

const COLLAPSE_KEY = 'onboarding-collapsed'

// The checklist copy. A step's blurb + cta only ever render while it is undone,
// so nothing here needs to know the live state.
const STEPS = [
  {
    title: 'Build your profile',
    blurb: 'Name, contact and links — filled into every application once.',
    cta: <Link to="/profile" className="ob-cta">Add your details →</Link>,
  },
  {
    title: 'Add a résumé',
    blurb: 'Save your .tex sources so each run tailors without a re-upload.',
    cta: <Link to="/library" className="ob-cta">Open the library →</Link>,
  },
  {
    title: 'Install the extension',
    blurb: 'Autofills the ATS form and attaches your tailored résumé — you review & submit.',
    cta: (
      <span className="font-mono text-[11px] text-cream-soft">
        Load unpacked from <code className="text-marigold">/extension</code> (see its README), then
        reload this page.
      </span>
    ),
  },
  {
    title: 'Tailor your first',
    blurb: 'Paste a job (or a link) and pick a résumé below — we do the rest.',
    cta: <span className="font-mono text-[11px] text-cream-soft">Set the brief just below ↓</span>,
  },
] as const

// First-run setup (T14): reads real state, guides profile → résumé → extension →
// first tailor. Dismissible (collapses to a slim bar) and resumable; disappears
// for good once every step is done. Native — no tour library.
export function Onboarding() {
  const progress = useSetupProgress()
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSE_KEY) === '1')

  if (!progress) return null // still loading — don't flash an empty checklist
  const doneCount = progress.filter(Boolean).length
  if (doneCount === STEPS.length) return null // setup complete → gone for good

  const collapse = () => {
    localStorage.setItem(COLLAPSE_KEY, '1')
    setCollapsed(true)
  }
  const expand = () => {
    localStorage.removeItem(COLLAPSE_KEY)
    setCollapsed(false)
  }

  if (collapsed) {
    return (
      <div className="mx-auto max-w-[96rem] px-6 pt-8">
        <button
          onClick={expand}
          className="flex w-full items-center gap-3 rounded-md border border-dashed border-cream-soft/25 px-4 py-2.5 text-left font-mono text-[11px] tracking-[0.16em] text-cream-soft uppercase transition hover:border-marigold/40 hover:text-cream"
        >
          <span className="text-marigold">◔</span>
          Getting set up · {doneCount} of {STEPS.length}
          <span aria-hidden className="ml-auto">resume ↓</span>
        </button>
      </div>
    )
  }

  return (
    <section
      aria-label="Setup checklist"
      className="mx-auto mt-8 max-w-[96rem] px-6"
    >
      <Sheet className="relative overflow-hidden p-6 lg:p-8">
        <div aria-hidden className="pointer-events-none absolute inset-y-0 left-0 w-[3px] bg-marigold" />
        <div className="mb-5 flex items-baseline justify-between gap-4">
          <div>
            <p className="font-mono text-[11px] tracking-[0.28em] text-accent uppercase">
              first — set up the desk
            </p>
            <h2 className="mt-1 font-serif text-2xl text-ink">
              {doneCount} of {STEPS.length} ready
            </h2>
          </div>
          <button
            onClick={collapse}
            className="shrink-0 font-mono text-[11px] tracking-[0.16em] text-ink-soft uppercase underline-offset-4 hover:text-ink hover:underline"
          >
            dismiss
          </button>
        </div>

        <ol className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <li key={s.title} className="flex gap-3">
              <span
                aria-hidden
                className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border font-mono text-[11px] ${
                  progress[i]
                    ? 'border-transparent bg-marigold text-ink'
                    : 'border-ink-soft/40 text-ink-soft'
                }`}
              >
                {progress[i] ? '✓' : i + 1}
              </span>
              <div className="space-y-0.5">
                <p className={`font-mono text-sm ${progress[i] ? 'text-ink-soft line-through' : 'text-ink'}`}>
                  {s.title}
                </p>
                {!progress[i] && (
                  <>
                    <p className="text-[13px] leading-snug text-ink-soft">{s.blurb}</p>
                    {s.cta}
                  </>
                )}
              </div>
            </li>
          ))}
        </ol>
      </Sheet>
    </section>
  )
}
