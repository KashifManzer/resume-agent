import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'motion/react'

import { Dropzone } from '@/components/Dropzone'
import { ListSkeleton } from '@/components/states/ListSkeleton'
import { Button } from '@/components/ui/button'
import { Kicker } from '@/components/ui/Kicker'
import { Sheet } from '@/components/ui/Sheet'
import { Textarea } from '@/components/ui/textarea'
import { useCreateJob, useJdFromUrl } from '@/hooks/useJobs'
import { useResumes } from '@/hooks/useProfile'
import { rise, stagger, useEntrance } from '@/lib/motion'

function Eyebrow({ n, children }: { n: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline gap-2.5 font-mono text-[11px] tracking-[0.22em] uppercase">
      <span className="text-marigold">{n}</span>
      <span className="text-cream-soft">{children}</span>
    </div>
  )
}

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

function Guarantees() {
  return (
    <motion.section
      variants={rise}
      aria-label="How the tailoring stays honest"
      className="border-y border-desk-line py-8 lg:col-span-2"
    >
      <div className="grid grid-cols-1 gap-x-8 gap-y-7 sm:grid-cols-2 lg:grid-cols-4">
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

export function Compose() {
  const navigate = useNavigate()
  const [jd, setJd] = useState('')
  const [link, setLink] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [selectedIds, setSelectedIds] = useState<string[] | null>(null) // null = not yet seeded
  const create = useCreateJob()
  const jdFetch = useJdFromUrl()
  const { data: resumes = [], isPending: resumesLoading } = useResumes()
  const entrance = useEntrance()

  // pre-check the default library résumé once, without clobbering user edits
  useEffect(() => {
    if (selectedIds === null && resumes.length > 0) {
      const def = resumes.find((r) => r.is_default) ?? resumes[0]
      // one-shot seed of the selection from the loaded library
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSelectedIds([def.id])
    }
  }, [resumes, selectedIds])

  const selected = selectedIds ?? []
  const toggle = (id: string) =>
    setSelectedIds((s) => {
      const cur = s ?? []
      return cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]
    })

  // ad-hoc upload wins if present; otherwise run from the library selection
  const canSubmit =
    jd.trim().length > 20 && (files.length > 0 || selected.length > 0) && !create.isPending

  function submit() {
    if (!canSubmit) return
    // T16: carry the adapter's apply URL (only set when the JD came from a link)
    // so the Result page can offer one-click "Apply with this résumé".
    const applyUrl = jdFetch.data?.apply_url ?? null
    const payload = files.length > 0 ? { jd, files, applyUrl } : { jd, resumeIds: selected, applyUrl }
    create.mutate(payload, { onSuccess: (r) => navigate(`/tailor/${r.job_id}`) })
  }

  function fetchLink() {
    const u = link.trim()
    if (!u || jdFetch.isPending) return
    jdFetch.mutate(u, { onSuccess: (src) => setJd(src.text) })
  }

  return (
    <motion.div
      variants={stagger}
      {...entrance}
      className="mx-auto grid max-w-6xl grid-cols-1 gap-x-14 gap-y-12 px-6 py-16 lg:grid-cols-[1.1fr_0.9fr] lg:py-24"
    >
      <motion.header variants={rise} className="lg:col-span-2">
        <Kicker>the proofing desk</Kicker>
        <h1 className="mt-4 max-w-3xl font-serif text-6xl leading-[0.9] font-medium tracking-[-0.02em] text-cream sm:text-7xl lg:text-8xl">
          Set the brief<span className="text-marigold">.</span>
        </h1>
        <p className="mt-6 max-w-xl text-lg leading-relaxed text-cream-soft">
          Paste the job description and lay your résumé sources on the desk. We&rsquo;ll pick the
          closest one, tailor it to the role &mdash; honestly, one page &mdash; and hand back a
          proofed PDF.
        </p>
      </motion.header>

      <Guarantees />

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
        <Sheet className="relative overflow-hidden">
          <div aria-hidden className="pointer-events-none absolute inset-y-0 left-11 w-px bg-gap/30" />
          <Textarea
            id="jd"
            value={jd}
            onChange={(e) => setJd(e.target.value)}
            placeholder="Paste the full job description…"
            className="min-h-[24rem] resize-y border-0 bg-transparent py-5 pr-5 pl-16 text-base leading-relaxed text-ink shadow-none placeholder:text-ink-soft/60 focus-visible:ring-0"
          />
        </Sheet>
      </motion.div>

      <motion.div variants={rise} className="flex flex-col gap-5">
        <Eyebrow n="02">your sources · .tex files</Eyebrow>

        {/* pick from the saved library (default pre-checked) — no forced re-upload */}
        {resumesLoading && <ListSkeleton rows={2} />}
        {!resumesLoading && resumes.length > 0 && (
          <div className="space-y-2">
            <Sheet as="ul" sm className="divide-y divide-border overflow-hidden">
              {resumes.map((r) => (
                <li key={r.id}>
                  <label className="flex cursor-pointer items-center gap-3 px-4 py-2.5">
                    <input
                      type="checkbox"
                      checked={selected.includes(r.id)}
                      onChange={() => toggle(r.id)}
                      className="size-4 accent-marigold"
                    />
                    <span className="truncate font-mono text-sm text-ink">{r.label || r.filename}</span>
                    {r.is_default && (
                      <span className="ml-auto shrink-0 rounded bg-marigold/20 px-2 py-0.5 font-mono text-[10px] tracking-[0.15em] text-marigold uppercase">
                        default
                      </span>
                    )}
                  </label>
                </li>
              ))}
            </Sheet>
            <p className="font-mono text-[11px] text-cream-soft">
              from your library — or upload a fresh one below (an upload takes precedence).
            </p>
          </div>
        )}

        {!resumesLoading && resumes.length === 0 && (
          <p className="font-mono text-[11px] leading-relaxed text-cream-soft">
            No saved résumés yet — drop one below for this run, or{' '}
            <Link to="/library" className="text-marigold underline-offset-2 hover:underline">
              add it to your library
            </Link>{' '}
            to reuse it on every run.
          </p>
        )}

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
            className="h-14 w-full rounded-md bg-marigold font-mono text-sm tracking-[0.2em] text-ink uppercase shadow-[0_10px_30px_-12px_rgba(243,180,31,0.7)] transition hover:bg-marigold hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-35 disabled:shadow-none"
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
