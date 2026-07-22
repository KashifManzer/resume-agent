import { useState } from 'react'
import { motion } from 'motion/react'

import { Dropzone } from '@/components/Dropzone'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { useCreateJob, useJdFromUrl } from '@/hooks/useJobs'

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.09, delayChildren: 0.05 } },
}
const rise = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] as const } },
}

function Eyebrow({ n, children }: { n: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline gap-2.5 font-mono text-[11px] tracking-[0.22em] uppercase">
      <span className="text-marigold">{n}</span>
      <span className="text-cream-soft">{children}</span>
    </div>
  )
}

export function Compose({ onCreated }: { onCreated: (id: string) => void }) {
  const [jd, setJd] = useState('')
  const [link, setLink] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const create = useCreateJob()
  const jdFetch = useJdFromUrl()
  const canSubmit = jd.trim().length > 20 && files.length > 0 && !create.isPending

  function submit() {
    if (!canSubmit) return
    create.mutate({ jd, files }, { onSuccess: (r) => onCreated(r.job_id) })
  }

  function fetchLink() {
    const u = link.trim()
    if (!u || jdFetch.isPending) return
    jdFetch.mutate(u, { onSuccess: (src) => setJd(src.text) })
  }

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="mx-auto grid max-w-6xl grid-cols-1 gap-x-14 gap-y-12 px-6 py-16 lg:grid-cols-[1.1fr_0.9fr] lg:py-24"
    >
      <motion.header variants={rise} className="lg:col-span-2">
        <p className="font-mono text-xs tracking-[0.34em] text-marigold uppercase">
          the proofing desk
        </p>
        <h1 className="mt-4 max-w-3xl font-serif text-6xl leading-[0.9] font-medium tracking-[-0.02em] text-cream sm:text-7xl lg:text-8xl">
          Set the brief<span className="text-marigold">.</span>
        </h1>
        <p className="mt-6 max-w-xl text-lg leading-relaxed text-cream-soft">
          Paste the job description and lay your résumé sources on the desk. We&rsquo;ll pick the
          closest one, tailor it to the role &mdash; honestly, one page &mdash; and hand back a
          proofed PDF.
        </p>
      </motion.header>

      <motion.div variants={rise} className="space-y-4">
        <label htmlFor="jd" className="block">
          <Eyebrow n="01">the brief · job description</Eyebrow>
        </label>

        {/* paste a job link → fills the JD field (Workday · Greenhouse · Lever · Ashby, else generic) */}
        <div className="space-y-2">
          <div className="flex gap-2">
            <input
              type="url"
              value={link}
              onChange={(e) => setLink(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), fetchLink())}
              placeholder="…or paste a job link (Workday · Greenhouse · Lever · Ashby)"
              className="min-w-0 flex-1 rounded-md border border-cream-soft/20 bg-transparent px-3 py-2.5 font-mono text-xs text-cream placeholder:text-cream-soft/50 focus:border-marigold focus:outline-none"
            />
            <Button
              onClick={fetchLink}
              disabled={!link.trim() || jdFetch.isPending}
              className="rounded-md bg-cream-soft/10 px-4 font-mono text-xs tracking-[0.15em] text-cream uppercase hover:bg-cream-soft/20 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {jdFetch.isPending ? 'fetching…' : 'fetch'}
            </Button>
          </div>
          {jdFetch.isError && (
            <p role="alert" className="font-mono text-xs text-gap-hi">
              {(jdFetch.error as Error).message}
            </p>
          )}
          {jdFetch.data && (
            <p className="font-mono text-xs text-cream-soft">
              filled from <span className="text-marigold">{jdFetch.data.adapter}</span>
              {jdFetch.data.title ? ` · ${jdFetch.data.title}` : ''} — review &amp; edit below before running.
            </p>
          )}
          {jdFetch.data?.warnings?.map((w) => (
            <p key={w} className="font-mono text-xs text-gap-hi">
              ⚠ {w}
            </p>
          ))}
        </div>

        {/* the brief, laid on a proofing sheet with a red margin rule */}
        <div className="sheet relative overflow-hidden">
          <div aria-hidden className="pointer-events-none absolute inset-y-0 left-11 w-px bg-gap/30" />
          <Textarea
            id="jd"
            value={jd}
            onChange={(e) => setJd(e.target.value)}
            placeholder="Paste the full job description…"
            className="min-h-[24rem] resize-y border-0 bg-transparent py-5 pr-5 pl-16 text-base leading-relaxed text-ink shadow-none placeholder:text-ink-soft/60 focus-visible:ring-0"
          />
        </div>
      </motion.div>

      <motion.div variants={rise} className="flex flex-col gap-5">
        <Eyebrow n="02">your sources · .tex files</Eyebrow>
        <Dropzone files={files} onChange={setFiles} />

        <div className="mt-auto space-y-3 pt-2">
          {create.isError && (
            <p role="alert" className="font-mono text-sm text-gap-hi">
              {(create.error as Error).message}
            </p>
          )}
          <Button
            onClick={submit}
            disabled={!canSubmit}
            className="h-14 w-full rounded-md bg-marigold font-mono text-sm tracking-[0.2em] text-ink uppercase shadow-[0_10px_30px_-12px_rgba(243,180,31,0.7)] transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-35 disabled:shadow-none"
          >
            {create.isPending ? 'sending to the press…' : 'Tailor my résumé →'}
          </Button>
          <p className="text-center font-mono text-xs text-cream-soft">
            a real run takes a few minutes — the LLM tailors, compiles &amp; scores.
          </p>
        </div>
      </motion.div>
    </motion.div>
  )
}
