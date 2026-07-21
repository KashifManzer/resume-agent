import { motion } from 'motion/react'

import { StepProgress } from '@/components/StepProgress'
import { Button } from '@/components/ui/button'
import type { Job } from '@/lib/types'

export function Run({ job, onStartOver }: { job: Job; onStartOver: () => void }) {
  if (job.status === 'error') {
    return (
      <div className="mx-auto max-w-2xl px-6 py-24 text-center">
        <p className="font-mono text-xs tracking-[0.3em] text-gap uppercase">the press jammed</p>
        <h2 className="mt-3 font-serif text-4xl text-ink">Something went wrong</h2>
        <p className="mx-auto mt-4 max-w-md font-mono text-sm text-ink-soft">{job.error}</p>
        <Button
          onClick={onStartOver}
          className="mt-8 h-11 rounded-md bg-ink px-6 font-mono text-sm tracking-widest text-primary-foreground uppercase hover:bg-ink/90"
        >
          Start over
        </Button>
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="mx-auto max-w-2xl px-6 py-20"
    >
      <p className="font-mono text-xs tracking-[0.3em] text-accent uppercase">
        {job.round > 0 ? `revision ${job.round}` : 'marking up the proof'}
      </p>
      <h2 className="mt-3 font-serif text-5xl leading-tight text-ink">
        Tailoring in progress<span className="text-accent">.</span>
      </h2>
      <p className="mt-3 font-serif text-lg text-ink-soft">
        Select &rarr; baseline &rarr; improve &rarr; quality gate. This takes a few minutes — leave
        it running.
      </p>

      <div className="mt-10 rounded-lg border border-border bg-paper-2/70 p-8">
        <StepProgress progress={job.progress} status={job.status} />
      </div>

      <button
        onClick={onStartOver}
        className="mt-8 font-mono text-xs tracking-widest text-ink-soft uppercase underline-offset-4 hover:text-ink hover:underline"
      >
        cancel &amp; start over
      </button>
    </motion.div>
  )
}
