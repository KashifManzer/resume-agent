import { motion } from 'motion/react'

import { rise, useEntrance } from '@/lib/motion'

// The honesty differentiator, told as an editorial spec band on the desk — the
// four things that make this tailoring trustworthy. Presentation only.
const PILLARS = [
  {
    tag: 'latex-native',
    title: 'Tailors your real .tex',
    body: 'We edit your actual LaTeX source and compile a true one-page PDF — never a lossy re-type.',
  },
  {
    tag: 'no fabrication',
    title: "Only what's yours",
    body: 'Nothing invented. Every claim we add to hit the match is surfaced for you to stand behind.',
  },
  {
    tag: 'grounded ATS',
    title: 'Scored on real keywords',
    body: "JD-fit measured against the posting's actual terms, before and after — no vanity number.",
  },
  {
    tag: 'quality gate',
    title: 'A hiring agent signs off',
    body: 'An independent hiring-agent reviews the result and must pass it before it reaches you.',
  },
] as const

// T21: first-run only. It earns its height while a new user is deciding whether
// to trust the desk; a set-up user gets the locked working screen instead, so
// this hangs off Home() next to Onboarding rather than inside Compose.
export function Guarantees() {
  const entrance = useEntrance()
  return (
    <motion.section
      variants={rise}
      {...entrance}
      aria-label="How the tailoring stays honest"
      className="mx-auto mt-10 max-w-[96rem] px-6"
    >
      <div className="grid grid-cols-1 gap-x-8 gap-y-7 border-y border-desk-line py-8 sm:grid-cols-2 lg:grid-cols-4">
        {PILLARS.map((p, i) => (
          <div key={p.tag}>
            <div className="flex items-baseline gap-2 font-mono text-[10px] tracking-[0.26em] uppercase">
              <span className="text-marigold tabular-nums">0{i + 1}</span>
              <span className="text-cream-soft">{p.tag}</span>
            </div>
            <h3 className="mt-2.5 font-serif text-xl leading-tight text-cream">{p.title}</h3>
            <p className="mt-1.5 text-[13px] leading-relaxed text-cream-soft">{p.body}</p>
          </div>
        ))}
      </div>
    </motion.section>
  )
}
