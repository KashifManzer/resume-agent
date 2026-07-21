import { AnimatePresence, motion } from 'motion/react'

import type { JobStatus } from '@/lib/types'

export function StepProgress({
  progress,
  status,
}: {
  progress: string[]
  status: JobStatus
}) {
  const steps = progress.length ? progress : ['queued — warming up the press']
  return (
    <ol className="space-y-3">
      <AnimatePresence initial={false}>
        {steps.map((step, i) => {
          const isLast = i === steps.length - 1
          const active = isLast && (status === 'running' || status === 'queued')
          return (
            <motion.li
              key={`${i}-${step}`}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
              className="flex items-center gap-3"
            >
              <span
                aria-hidden
                className={
                  active
                    ? 'font-serif text-accent'
                    : 'font-serif text-accent/80'
                }
              >
                {active ? (
                  <motion.span
                    animate={{ rotate: [0, -12, 0], opacity: [1, 0.5, 1] }}
                    transition={{ repeat: Infinity, duration: 1.4 }}
                    className="inline-block"
                  >
                    ✎
                  </motion.span>
                ) : (
                  '✓'
                )}
              </span>
              <span
                className={
                  active
                    ? 'font-serif text-lg text-ink'
                    : 'font-serif text-lg text-ink-soft'
                }
              >
                {step}
              </span>
            </motion.li>
          )
        })}
      </AnimatePresence>
    </ol>
  )
}
