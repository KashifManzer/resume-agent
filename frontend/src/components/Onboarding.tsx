import { useState } from 'react'
import { Link } from 'react-router-dom'

import { useExtensionInstalled } from '@/hooks/useExtension'
import { useJobsList } from '@/hooks/useJobs'
import { useProfile, useResumes } from '@/hooks/useProfile'

const COLLAPSE_KEY = 'onboarding-collapsed'

interface Step {
  done: boolean
  title: string
  blurb: React.ReactNode
  cta: React.ReactNode
}

// First-run setup (T14): reads real state, guides profile → résumé → extension →
// first tailor. Dismissible (collapses to a slim bar) and resumable; disappears
// for good once every step is done. Native — no tour library.
export function Onboarding() {
  const { data: profile } = useProfile()
  const { data: resumes = [] } = useResumes()
  const { data: jobs = [] } = useJobsList()
  const extension = useExtensionInstalled()
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSE_KEY) === '1')

  const steps: Step[] = [
    {
      done: Boolean(profile?.name || profile?.email),
      title: 'Build your profile',
      blurb: 'Name, contact and links — filled into every application once.',
      cta: <Link to="/profile" className="ob-cta">Add your details →</Link>,
    },
    {
      done: resumes.length > 0,
      title: 'Add a résumé',
      blurb: 'Save your .tex sources so each run tailors without a re-upload.',
      cta: <Link to="/library" className="ob-cta">Open the library →</Link>,
    },
    {
      done: extension,
      title: 'Install the extension',
      blurb: 'Autofills the ATS form and attaches your tailored résumé — you review & submit.',
      cta: extension ? null : (
        <span className="font-mono text-[11px] text-cream-soft">
          Load unpacked from <code className="text-marigold">/extension</code> (see its README), then
          reload this page.
        </span>
      ),
    },
    {
      done: jobs.length > 0,
      title: 'Tailor your first',
      blurb: 'Paste a job (or a link) and pick a résumé below — we do the rest.',
      cta: <span className="font-mono text-[11px] text-cream-soft">Set the brief just below ↓</span>,
    },
  ]

  const doneCount = steps.filter((s) => s.done).length
  if (doneCount === steps.length) return null // setup complete → gone for good

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
      <div className="mx-auto max-w-6xl px-6 pt-8">
        <button
          onClick={expand}
          className="flex w-full items-center gap-3 rounded-md border border-dashed border-cream-soft/25 px-4 py-2.5 text-left font-mono text-[11px] tracking-[0.16em] text-cream-soft uppercase transition hover:border-marigold/40 hover:text-cream"
        >
          <span className="text-marigold">◔</span>
          Getting set up · {doneCount} of {steps.length}
          <span aria-hidden className="ml-auto">resume ↓</span>
        </button>
      </div>
    )
  }

  return (
    <section
      aria-label="Setup checklist"
      className="mx-auto mt-8 max-w-6xl px-6"
    >
      <div className="sheet relative overflow-hidden p-6 lg:p-8">
        <div aria-hidden className="pointer-events-none absolute inset-y-0 left-0 w-[3px] bg-marigold" />
        <div className="mb-5 flex items-baseline justify-between gap-4">
          <div>
            <p className="font-mono text-[11px] tracking-[0.28em] text-accent uppercase">
              first — set up the desk
            </p>
            <h2 className="mt-1 font-serif text-2xl text-ink">
              {doneCount} of {steps.length} ready
            </h2>
          </div>
          <button
            onClick={collapse}
            className="shrink-0 font-mono text-[11px] tracking-[0.16em] text-ink-soft uppercase underline-offset-4 hover:text-ink hover:underline"
          >
            dismiss
          </button>
        </div>

        <ol className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2">
          {steps.map((s, i) => (
            <li key={i} className="flex gap-3">
              <span
                aria-hidden
                className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border font-mono text-[11px] ${
                  s.done
                    ? 'border-transparent bg-marigold text-ink'
                    : 'border-ink-soft/40 text-ink-soft'
                }`}
              >
                {s.done ? '✓' : i + 1}
              </span>
              <div className="space-y-0.5">
                <p className={`font-mono text-sm ${s.done ? 'text-ink-soft line-through' : 'text-ink'}`}>
                  {s.title}
                </p>
                {!s.done && (
                  <>
                    <p className="text-[13px] leading-snug text-ink-soft">{s.blurb}</p>
                    {s.cta}
                  </>
                )}
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
