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
      className="mx-auto max-w-7xl px-6 py-12"
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

      <div className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr]">
        {/* Left: the proofed page itself, large and readable. */}
        <motion.div variants={section} className="lg:sticky lg:top-6 lg:self-start">
          <iframe
            title="Tailored résumé (PDF)"
            src={`${pdfUrl(jobId)}?r=${round}`}
            className="h-[82vh] w-full rounded-md border border-ink/25 bg-white shadow-[0_18px_40px_-20px_rgba(36,28,18,0.5)]"
          />
          <div className="mt-4 flex gap-3">
            <a
              href={pdfUrl(jobId)}
              download="resume.pdf"
              className="inline-flex h-11 flex-1 items-center justify-center rounded-md bg-ink font-mono text-sm tracking-widest text-primary-foreground uppercase transition-colors hover:bg-ink/90 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              Download PDF
            </a>
            <Button
              variant="outline"
              onClick={() => downloadTex(result.tex)}
              className="h-11 flex-1 rounded-md border-ink/30 font-mono text-sm tracking-widest text-ink uppercase hover:bg-paper"
            >
              Download .tex
            </Button>
          </div>
        </motion.div>

        {/* Right: the marks — scores, coverage, what we added, revisions. */}
        <div className="space-y-8">
          <motion.div variants={section}>
            <ScoreReveal before={report.ats_before.overall} after={report.ats_after.overall} />
          </motion.div>

          <motion.section variants={section}>
            <h2 className="mb-4 font-serif text-2xl text-ink">Keyword coverage</h2>
            <KeywordMarks matched={report.ats_after.matched} missing={report.ats_after.missing} />
          </motion.section>

          {report.added.length > 0 && (
            <motion.section variants={section} className="rounded-lg border border-accent/30 bg-accent/5 p-5">
              <h2 className="font-serif text-2xl text-ink">Added — review these</h2>
              <p className="mt-1 mb-3 text-sm text-ink-soft">
                We wrote these in to hit the match. They&rsquo;re now claims on your résumé &mdash;
                make sure you can speak to each one in an interview.
              </p>
              <div className="flex flex-wrap gap-x-1.5 gap-y-2 font-serif text-lg">
                {report.added.map((a) => (
                  <span key={a} className="mark-hl">
                    {a}
                  </span>
                ))}
              </div>
            </motion.section>
          )}

          {report.changes.length > 0 && (
            <motion.section variants={section}>
              <h2 className="mb-3 font-serif text-2xl text-ink">What changed</h2>
              <ul className="space-y-2">
                {report.changes.map((c, i) => (
                  <li key={i} className="border-l-2 border-accent/40 pl-3 font-serif text-ink">
                    {c}
                  </li>
                ))}
              </ul>
            </motion.section>
          )}

          {report.hiring_agent && (
            <motion.div variants={section}>
              <HiringAgentCard report={report.hiring_agent} />
            </motion.div>
          )}

          <motion.div variants={section}>
            <FeedbackBox jobId={jobId} round={round} />
          </motion.div>
        </div>
      </div>
    </motion.div>
  )
}
