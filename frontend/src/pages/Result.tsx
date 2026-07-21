import { motion } from 'motion/react'

import { FeedbackBox } from '@/components/FeedbackBox'
import { HiringAgentCard } from '@/components/HiringAgentCard'
import { KeywordMarks } from '@/components/KeywordMarks'
import { ScoreReveal } from '@/components/ScoreReveal'
import { Button } from '@/components/ui/button'
import { downloadTex, pdfUrl } from '@/lib/api'
import type { PipelineResult } from '@/lib/types'

const section = {
  hidden: { opacity: 0, y: 18 },
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
      className="mx-auto max-w-7xl px-6 py-14 lg:py-20"
    >
      <motion.header variants={section} className="mb-10 flex items-end justify-between gap-6">
        <div>
          <p className="font-mono text-xs tracking-[0.34em] text-marigold uppercase">
            proof approved
          </p>
          <h1 className="mt-3 font-serif text-5xl leading-[0.95] tracking-[-0.02em] text-cream sm:text-6xl lg:text-7xl">
            Your tailored résumé
          </h1>
        </div>
        <button
          onClick={onStartOver}
          className="shrink-0 pb-2 font-mono text-xs tracking-[0.2em] text-cream-soft uppercase underline-offset-4 transition hover:text-cream hover:underline"
        >
          new brief →
        </button>
      </motion.header>

      {report.selection_warning && (
        <motion.div
          variants={section}
          role="alert"
          className="sheet-sm mb-10 border-l-[3px] border-l-gap px-5 py-3.5 text-ink"
        >
          <span className="font-mono text-xs tracking-[0.2em] text-gap uppercase">note · </span>
          {report.selection_warning}
        </motion.div>
      )}

      <div className="grid grid-cols-1 gap-10 lg:grid-cols-[1.12fr_0.88fr]">
        {/* Left: the proofed page itself — a physical sheet on the desk, stamped. */}
        <motion.div variants={section} className="lg:sticky lg:top-8 lg:self-start">
          <div className="relative">
            <div className="stamp stamp-in absolute -top-6 -right-5 z-10 text-[0.72rem] leading-tight tracking-[0.16em]">
              <span>Proof</span>
              <span>Approved</span>
              <span className="mt-0.5 text-[0.5rem] tracking-[0.14em] opacity-80">
                one page · {new Date().getFullYear()}
              </span>
            </div>
            <div className="sheet overflow-hidden p-2.5">
              <iframe
                title="Tailored résumé (PDF)"
                src={`${pdfUrl(jobId)}?r=${round}`}
                className="h-[80vh] w-full rounded-sm bg-white"
              />
            </div>
          </div>
          <div className="mt-5 flex gap-3">
            <a
              href={pdfUrl(jobId)}
              download="resume.pdf"
              className="inline-flex h-12 flex-1 items-center justify-center rounded-md bg-marigold font-mono text-sm tracking-[0.18em] text-ink uppercase shadow-[0_10px_28px_-12px_rgba(243,180,31,0.7)] transition hover:brightness-95 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-desk focus-visible:outline-none"
            >
              Download PDF
            </a>
            <Button
              variant="outline"
              onClick={() => downloadTex(result.tex)}
              className="h-12 flex-1 rounded-md border-cream/25 bg-transparent font-mono text-sm tracking-[0.18em] text-cream uppercase hover:bg-cream/10 hover:text-cream"
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

          <motion.section variants={section} className="sheet p-7">
            <h2 className="mb-5 font-serif text-2xl text-ink">Keyword coverage</h2>
            <KeywordMarks matched={report.ats_after.matched} missing={report.ats_after.missing} />
          </motion.section>

          {report.added.length > 0 && (
            <motion.section
              variants={section}
              className="sheet border-l-[3px] border-l-marigold p-7"
            >
              <h2 className="font-serif text-2xl text-ink">Added — review these</h2>
              <p className="mt-1.5 mb-4 text-sm leading-relaxed text-ink-soft">
                We wrote these in to hit the match. They&rsquo;re now claims on your résumé &mdash;
                make sure you can speak to each one in an interview.
              </p>
              <div className="flex flex-wrap gap-x-1.5 gap-y-2.5 text-lg">
                {report.added.map((a) => (
                  <span key={a} className="mark-hl">
                    {a}
                  </span>
                ))}
              </div>
            </motion.section>
          )}

          {report.changes.length > 0 && (
            <motion.section variants={section} className="sheet p-7">
              <h2 className="mb-4 font-serif text-2xl text-ink">What changed</h2>
              <ul className="space-y-3">
                {report.changes.map((c, i) => (
                  <li key={i} className="flex gap-3 text-ink">
                    <span aria-hidden className="mt-1.5 font-mono text-xs text-marigold tabular-nums">
                      {String(i + 1).padStart(2, '0')}
                    </span>
                    <span className="leading-relaxed">{c}</span>
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
