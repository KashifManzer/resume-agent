import { motion } from 'motion/react'

import { StepProgress } from '@/components/StepProgress'
import type { Job } from '@/lib/types'

export function Run({ job, onStartOver }: { job: Job; onStartOver: () => void }) {
  if (job.status === 'error') {
    return (
      <div className="mx-auto max-w-2xl px-6 py-28 text-center">
        <p className="font-mono text-xs tracking-[0.34em] text-gap-hi uppercase">the press jammed</p>
        <h2 className="mt-4 font-serif text-5xl text-cream">Something went wrong</h2>
        <p className="mx-auto mt-4 max-w-md font-mono text-sm text-cream-soft">{job.error}</p>
        <button
          onClick={onStartOver}
          className="mt-9 h-12 rounded-md border border-cream/25 px-7 font-mono text-sm tracking-[0.2em] text-cream uppercase transition hover:bg-cream/10 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          Start over
        </button>
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="mx-auto max-w-3xl px-6 py-20 lg:py-28"
    >
      <div className="flex items-center gap-3">
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-marigold opacity-70" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-marigold" />
        </span>
        <p className="font-mono text-xs tracking-[0.34em] text-marigold uppercase">
          {job.round > 0 ? `revision ${job.round} · marking` : 'marking up the proof'}
        </p>
      </div>

      <h2 className="mt-5 font-serif text-6xl leading-[0.95] tracking-[-0.02em] text-cream lg:text-7xl">
        Tailoring in progress<span className="text-marigold">.</span>
      </h2>
      <p className="mt-5 max-w-xl text-lg leading-relaxed text-cream-soft">
        Select &rarr; baseline &rarr; improve &rarr; quality gate. This takes a few minutes — leave it
        running while the press marks the proof.
      </p>

      <div className="sheet mt-12 p-8 lg:p-10">
        <div className="mb-6 flex items-baseline justify-between border-b border-paper-line pb-4">
          <span className="font-mono text-[11px] tracking-[0.28em] text-ink-soft uppercase">
            proof marks
          </span>
          <span className="font-mono text-[11px] tracking-[0.28em] text-accent uppercase">live</span>
        </div>
        <StepProgress progress={job.progress} status={job.status} />
      </div>

      <button
        onClick={onStartOver}
        className="mt-8 font-mono text-xs tracking-[0.2em] text-cream-soft uppercase underline-offset-4 transition hover:text-cream hover:underline"
      >
        cancel &amp; start over
      </button>
    </motion.div>
  )
}
