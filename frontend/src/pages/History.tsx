import { Link } from 'react-router-dom'

import { PageHeading } from '@/components/PageHeading'
import { useJobsList } from '@/hooks/useJobs'
import type { JobStatus, JobSummary } from '@/lib/types'

function timeAgo(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

const STATUS: Record<JobStatus, { label: string; cls: string }> = {
  done: { label: 'proofed', cls: 'bg-marigold/20 text-marigold' },
  running: { label: 'on the press', cls: 'bg-cream-soft/15 text-cream-soft' },
  queued: { label: 'queued', cls: 'bg-cream-soft/15 text-cream-soft' },
  error: { label: 'jammed', cls: 'bg-gap/20 text-gap-hi' },
}

// Run history (T14) over GET /jobs — the same endpoint the extension picker
// reads. Each row reopens into its /tailor/:id route (Result if it finished).
export function History() {
  const { data: jobs, isLoading, isError } = useJobsList()

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-6 py-16 lg:py-20">
      <PageHeading kicker="set up & track · history" title={<>Past proofs<span className="text-marigold">.</span></>}>
        Every run you&rsquo;ve sent to the press. Reopen one to view its proof, scores and the
        tailored PDF.
      </PageHeading>

      {isLoading && (
        <p className="font-mono text-sm tracking-[0.2em] text-cream-soft uppercase">loading runs…</p>
      )}
      {isError && (
        <p role="alert" className="font-mono text-sm text-gap-hi">
          Couldn&rsquo;t load your history — is the backend running?
        </p>
      )}

      {jobs && jobs.length === 0 && (
        <div className="sheet-sm border-l-[3px] border-l-marigold px-5 py-4 text-ink">
          <p className="font-serif text-lg">Nothing filed yet.</p>
          <p className="mt-1 text-sm text-ink-soft">
            <Link to="/" className="text-accent underline-offset-2 hover:underline">
              Tailor your first résumé
            </Link>{' '}
            and it&rsquo;ll land here.
          </p>
        </div>
      )}

      {jobs && jobs.length > 0 && (
        <ul className="sheet-sm divide-y divide-border overflow-hidden">
          {jobs.map((j) => (
            <Row key={j.id} job={j} />
          ))}
        </ul>
      )}
    </div>
  )
}

function Row({ job }: { job: JobSummary }) {
  const s = STATUS[job.status]
  return (
    <li>
      <Link
        to={`/tailor/${job.id}`}
        className="group flex items-center gap-3 px-4 py-3.5 transition hover:bg-paper-edge focus-visible:bg-paper-edge focus-visible:outline-none"
      >
        <span className="min-w-0 flex-1">
          <span className="block truncate font-mono text-sm text-ink">{job.title}</span>
          <span className="font-mono text-[11px] text-ink-soft">{timeAgo(job.created_at)}</span>
        </span>
        <span
          className={`shrink-0 rounded px-2 py-0.5 font-mono text-[10px] tracking-[0.15em] uppercase ${s.cls}`}
        >
          {s.label}
        </span>
        <span
          aria-hidden
          className="shrink-0 font-mono text-sm text-ink-soft transition-transform group-hover:translate-x-0.5"
        >
          →
        </span>
      </Link>
    </li>
  )
}
