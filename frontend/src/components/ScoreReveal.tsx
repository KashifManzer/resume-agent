import { motion } from 'motion/react'

import { CountUp } from './CountUp'

/** The signature moment: JD-fit before → after, delta animated. */
export function ScoreReveal({ before, after }: { before: number; after: number }) {
  const delta = after - before
  return (
    <div className="relative overflow-hidden rounded-lg border border-border bg-paper-2/80 p-8">
      <span className="font-mono text-[11px] tracking-[0.25em] text-ink-soft uppercase">
        JD-fit / ATS
      </span>

      <div className="mt-5 flex items-end gap-6">
        <div>
          <div className="font-mono text-xs text-ink-soft">before</div>
          <div className="font-mono text-5xl text-ink-soft/70 tabular-nums line-through decoration-ink-soft/40 decoration-1">
            {before}
          </div>
        </div>

        <motion.div
          aria-hidden
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.4 }}
          className="pb-4 font-serif text-3xl text-accent"
        >
          →
        </motion.div>

        <div>
          <div className="font-mono text-xs text-accent">after</div>
          <div className="flex items-baseline font-mono text-7xl leading-none text-ink tabular-nums">
            <CountUp to={after} delay={0.4} />
            <span className="ml-1 text-2xl text-ink-soft">/100</span>
          </div>
        </div>

        {delta !== 0 && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1.4 }}
            className="mb-2 ml-auto rounded-sm bg-highlight/70 px-2 py-1 font-mono text-sm text-ink"
          >
            {delta > 0 ? '+' : ''}
            {delta}
          </motion.div>
        )}
      </div>
    </div>
  )
}
