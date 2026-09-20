import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { motion } from 'motion/react'

import { Dropzone } from '@/components/Dropzone'
import { ListSkeleton } from '@/components/states/ListSkeleton'
import { Button } from '@/components/ui/button'
import { Kicker } from '@/components/ui/Kicker'
import { Sheet } from '@/components/ui/Sheet'
import { Textarea } from '@/components/ui/textarea'
import { useCreateJob, useJdFromUrl, useJdHandoff } from '@/hooks/useJobs'
import { ApiError } from '@/lib/api'
import { useResumes } from '@/hooks/useProfile'
import { markTailored } from '@/hooks/useSetup'
import { rise, stagger, useEntrance } from '@/lib/motion'

function Eyebrow({ n, children }: { n: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline gap-2.5 font-mono text-[11px] tracking-[0.22em] uppercase">
      <span className="text-marigold">{n}</span>
      <span className="text-cream-soft">{children}</span>
    </div>
  )
}

// The working screen (T21): on a real desk (`desk:` — wide and tall enough) this
// fills the viewport exactly and never scrolls the page. The brief and the
// sources scroll *inside* their columns, so the Tailor button stays in view no
// matter how long the JD is. Anything smaller falls back to natural scroll.
export function Compose() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const initialUrl = params.get('url') || ''
  const [draft, setJd] = useState<string | null>(null)
  const [link, setLink] = useState(initialUrl)
  const [files, setFiles] = useState<File[]>([])
  const [selectedIds, setSelectedIds] = useState<string[] | null>(null) // null = not yet seeded
  const create = useCreateJob()
  const jdFetch = useJdFromUrl()
  const fromBoard = params.get('from') === 'board'
  const handoff = useJdHandoff(initialUrl, fromBoard)
  const source = jdFetch.data ?? handoff.data
  // Only a pristine field follows the automatic result. Even an intentional
  // edit to an empty string must survive a slow fetch or a retry.
  const jd = draft ?? source?.text ?? ''
  const unavailable = handoff.error instanceof ApiError && [404, 410].includes(handoff.error.status)

  const { data: resumes = [], isPending: resumesLoading } = useResumes()
  const entrance = useEntrance()

  // pre-check the whole library once (the selector picks the JD-closest across
  // all of them), without clobbering user edits
  useEffect(() => {
    if (selectedIds === null && resumes.length > 0) {
      // one-shot seed of the selection from the loaded library
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSelectedIds(resumes.map((r) => r.id))
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
    jd.trim().length > 20 && (files.length > 0 || selected.length > 0) && !create.isPending && !handoff.isFetching

  function submit() {
    if (!canSubmit) return
    // T16: carry the adapter's apply URL (only set when the JD came from a link)
    // so the Result page can offer one-click "Apply with this résumé".
    const applyUrl = source?.apply_url ?? null
    const payload = files.length > 0 ? { jd, files, applyUrl } : { jd, resumeIds: selected, applyUrl }
    create.mutate(payload, {
      onSuccess: (r) => {
        markTailored() // outlives the in-memory job list, so setup stays "done"
        navigate(`/tailor/${r.job_id}`)
      },
    })
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
      className="mx-auto flex max-w-[96rem] flex-col gap-9 px-6 py-12 desk:h-full desk:gap-7 desk:overflow-hidden desk:py-8"
    >
      {/* the masthead: title left, the deck alongside it — a slim working header,
          not a landing hero, so the desk itself is above the fold */}
      <motion.header
        variants={rise}
        className="flex shrink-0 flex-wrap items-end justify-between gap-x-14 gap-y-4 border-b border-desk-line pb-6"
      >
        <div>
          <Kicker>the proofing desk</Kicker>
          <h1 className="mt-3 font-serif text-5xl leading-[0.9] font-medium tracking-[-0.02em] text-cream sm:text-6xl">
            Set the brief<span className="text-marigold">.</span>
          </h1>
        </div>
        <p className="max-w-lg text-sm leading-relaxed text-cream-soft sm:text-right">
          Paste the job description and lay your résumé sources on the desk. We&rsquo;ll pick the
          closest one, tailor it to the role &mdash; honestly, one page &mdash; and hand back a
          proofed PDF.
        </p>
      </motion.header>

      <div className="grid grid-cols-1 gap-x-14 gap-y-12 desk:min-h-0 desk:flex-1 lg:grid-cols-[1.1fr_0.9fr]">
        <motion.div variants={rise} className="flex flex-col gap-4 desk:min-h-0">
          <label htmlFor="jd" className="block shrink-0">
            <Eyebrow n="01">the brief · job description</Eyebrow>
          </label>

          {/* paste a job link → fills the JD field (Workday · Greenhouse · Lever · Ashby, else generic) */}
          <div className="shrink-0 space-y-2">
            {initialUrl && !jdFetch.data && (
              <>
                {handoff.isFetching && (
                  <p role="status" className="font-mono text-xs text-cream-soft">
                    {fromBoard ? 'Checking this posting and fetching its description…' : 'Fetching the job description…'}
                  </p>
                )}
                {handoff.isError && (
                  <div role="alert" className="space-y-2 border-l-2 border-gap-hi pl-3 py-1">
                    <p className="font-mono text-xs text-gap-hi">{handoff.error.message}</p>
                    <div className="flex items-center gap-4 font-mono text-xs">
                      {!unavailable && (
                        <button type="button" onClick={() => void handoff.refetch()} disabled={handoff.isFetching}
                          className="text-cream underline underline-offset-4 disabled:opacity-40">Retry</button>
                      )}
                      {fromBoard && <Link to="/board" className="text-marigold underline underline-offset-4">Back to Board</Link>}
                    </div>
                  </div>
                )}
              </>
            )}
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
            {source && (
              <p className="font-mono text-xs text-cream-soft">
                filled from <span className="text-marigold">{source.adapter}</span>
                {source.title ? ` · ${source.title}` : ''} — review &amp; edit below before running.
              </p>
            )}
            {source?.warnings?.map((w) => (
              <p key={w} className="font-mono text-xs text-gap-hi">
                ⚠ {w}
              </p>
            ))}
          </div>

          {/* the brief, laid on a proofing sheet with a red margin rule. The sheet
              fills the column and the paste scrolls *inside* it — a long JD never
              grows the page. */}
          <Sheet className="relative overflow-hidden desk:min-h-0 desk:flex-1">
            <div aria-hidden className="pointer-events-none absolute inset-y-0 left-11 w-px bg-gap/30" />
            <Textarea
              id="jd"
              value={jd}
              onChange={(e) => setJd(e.target.value)}
              placeholder="Paste the full job description…"
              className="h-96 resize-none field-sizing-fixed overflow-y-auto border-0 bg-transparent py-5 pr-5 pl-16 text-base leading-relaxed text-ink shadow-none placeholder:text-ink-soft/60 focus-visible:ring-0 desk:h-full"
            />
          </Sheet>
        </motion.div>

        <motion.div variants={rise} className="flex flex-col gap-5 desk:min-h-0">
          <Eyebrow n="02">your sources · .tex files</Eyebrow>

          {/* pick from the saved library (all pre-checked) — no forced re-upload.
              A long library scrolls here rather than pushing the button off-screen;
              the slack goes to the drop target below, not to a hole in the column. */}
          <div className="space-y-2 desk:max-h-[45%] desk:shrink-0 desk:overflow-y-auto">
            {resumesLoading && <ListSkeleton rows={2} />}
            {!resumesLoading && resumes.length > 0 && (
              <>
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
                  all selected — we pick the closest; uncheck any to exclude. an upload wins.
                </p>
              </>
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
          </div>

          <Dropzone files={files} onChange={setFiles} className="desk:min-h-0 desk:flex-1" />

          <div className="shrink-0 space-y-3 pt-2">
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
      </div>
    </motion.div>
  )
}
