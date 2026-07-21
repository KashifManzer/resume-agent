import { useState } from 'react'
import { motion } from 'motion/react'

import { Dropzone } from '@/components/Dropzone'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { useCreateJob } from '@/hooks/useJobs'

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.09, delayChildren: 0.05 } },
}
const rise = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] as const } },
}

export function Compose({ onCreated }: { onCreated: (id: string) => void }) {
  const [jd, setJd] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const create = useCreateJob()
  const canSubmit = jd.trim().length > 20 && files.length > 0 && !create.isPending

  function submit() {
    if (!canSubmit) return
    create.mutate({ jd, files }, { onSuccess: (r) => onCreated(r.job_id) })
  }

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="mx-auto grid max-w-6xl gap-x-16 gap-y-10 px-6 py-16 lg:grid-cols-[1.15fr_0.85fr]"
    >
      <motion.header variants={rise} className="lg:col-span-2">
        <p className="font-mono text-xs tracking-[0.3em] text-accent uppercase">the proofing desk</p>
        <h1 className="mt-3 max-w-2xl font-serif text-6xl leading-[0.95] font-medium tracking-tight text-ink">
          Set the brief.
        </h1>
        <p className="mt-4 max-w-xl font-serif text-lg text-ink-soft">
          Paste the job description and lay your résumé sources on the desk. We&rsquo;ll pick the
          closest one, tailor it to the role &mdash; honestly, one page &mdash; and hand back a
          proofed PDF.
        </p>
      </motion.header>

      <motion.div variants={rise} className="space-y-3">
        <label htmlFor="jd" className="block font-mono text-[11px] tracking-[0.2em] text-ink-soft uppercase">
          job description
        </label>
        <Textarea
          id="jd"
          value={jd}
          onChange={(e) => setJd(e.target.value)}
          placeholder="Paste the full job description…"
          className="min-h-[22rem] resize-y border-ink/20 bg-paper-2/60 font-serif text-base leading-relaxed text-ink placeholder:text-ink-soft/60 focus-visible:ring-accent"
        />
      </motion.div>

      <motion.div variants={rise} className="flex flex-col gap-5">
        <Dropzone files={files} onChange={setFiles} />

        <div className="mt-auto space-y-3">
          {create.isError && (
            <p role="alert" className="font-mono text-sm text-gap">
              {(create.error as Error).message}
            </p>
          )}
          <Button
            onClick={submit}
            disabled={!canSubmit}
            className="h-12 w-full rounded-md bg-ink font-mono text-sm tracking-widest text-primary-foreground uppercase hover:bg-ink/90 disabled:opacity-40"
          >
            {create.isPending ? 'sending to the press…' : 'Tailor my résumé'}
          </Button>
          <p className="text-center font-mono text-xs text-ink-soft">
            a real run takes a few minutes — the LLM tailors, compiles &amp; scores.
          </p>
        </div>
      </motion.div>
    </motion.div>
  )
}
