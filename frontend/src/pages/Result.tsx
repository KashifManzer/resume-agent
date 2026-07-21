import { motion } from 'motion/react'

import { FeedbackBox } from '@/components/FeedbackBox'
import { HiringAgentCard } from '@/components/HiringAgentCard'
import { KeywordMarks } from '@/components/KeywordMarks'
import { ScoreReveal } from '@/components/ScoreReveal'
import { Button } from '@/components/ui/button'
import { downloadTex, pdfUrl } from '@/lib/api'
import type { PipelineResult } from '@/lib/types'

const section = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] as const } },
}

export function Result({
  jobId,
  round,
  result,
  onStartOver,
}: {
  jobId: string
  round: number
  result: PipelineResult
  onStartOver: () => void
}) {
  const { report } = result

  return (
    <motion.div
      initial="hidden"
      animate="show"
      transition={{ staggerChildren: 0.12 }}
      className="mx-auto max-w-6xl px-6 py-14"
    >
      <motion.header variants={section} className="mb-8 flex items-baseline justify-between">
        <div>
          <p className="font-mono text-xs tracking-[0.3em] text-accent uppercase">proof approved</p>
          <h1 className="mt-2 font-serif text-5xl leading-tight text-ink">Your tailored résumé</h1>
        </div>
        <button
          onClick={onStartOver}
          className="font-mono text-xs tracking-widest text-ink-soft uppercase underline-offset-4 hover:text-ink hover:underline"
        >
          new brief
        </button>
      </motion.header>

      {report.selection_warning && (
        <motion.div
          variants={section}
          role="alert"
          className="mb-8 rounded-md border border-gap/40 bg-gap/5 px-5 py-3 font-serif text-ink"
        >
          <span className="font-mono text-xs tracking-widest text-gap uppercase">note · </span>
          {report.selection_warning}
        </motion.div>
      )}

      <motion.div variants={section}>
        <ScoreReveal before={report.ats_before.overall} after={report.ats_after.overall} />
      </motion.div>

      <div className="mt-8 grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-8">
          <motion.section variants={section}>
            <h2 className="mb-4 font-serif text-2xl text-ink">Keyword coverage</h2>
            <KeywordMarks matched={report.ats_after.matched} missing={report.ats_after.missing} />
          </motion.section>

          {report.changes.length > 0 && (
            <motion.section variants={section}>
              <h2 className="mb-3 font-serif text-2xl text-ink">What changed</h2>
              <ul className="space-y-2">
                {report.changes.map((c, i) => (
                  <li key={i} className="flex gap-2 border-l-2 border-accent/40 pl-3 text-ink">
                    <span className="font-serif">{c}</span>
                  </li>
                ))}
              </ul>
            </motion.section>
          )}

          {report.could_not_add.length > 0 && (
            <motion.section variants={section}>
              <h2 className="mb-1 font-serif text-2xl text-ink">Left out, on purpose</h2>
              <p className="mb-3 text-sm text-ink-soft">
                The JD wanted these, but your résumé doesn&rsquo;t evidence them — we won&rsquo;t
                invent them. To genuinely raise your fit, earn and add them:
              </p>
              <div className="flex flex-wrap gap-x-3 gap-y-1 font-serif text-lg">
                {report.could_not_add.map((k) => (
                  <span key={k} className="mark-gap">
                    {k}
                  </span>
                ))}
              </div>
            </motion.section>
          )}
        </div>

        <aside className="space-y-6">
          <motion.section
            variants={section}
            className="rounded-lg border border-border bg-paper-2/80 p-6"
          >
            <h3 className="mb-4 font-serif text-xl text-ink">Take it with you</h3>
            <div className="flex flex-col gap-3">
              <a
                href={pdfUrl(jobId)}
                download="resume.pdf"
                className="inline-flex h-11 items-center justify-center rounded-md bg-ink font-mono text-sm tracking-widest text-primary-foreground uppercase transition-colors hover:bg-ink/90 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                Download PDF
              </a>
              <Button
                variant="outline"
                onClick={() => downloadTex(result.tex)}
                className="h-11 rounded-md border-ink/30 font-mono text-sm tracking-widest text-ink uppercase hover:bg-paper"
              >
                Download .tex
              </Button>
            </div>
          </motion.section>

          {report.hiring_agent && (
            <motion.div variants={section}>
              <HiringAgentCard report={report.hiring_agent} />
            </motion.div>
          )}

          <motion.div variants={section}>
            <FeedbackBox jobId={jobId} round={round} />
          </motion.div>
        </aside>
      </div>
    </motion.div>
  )
}
