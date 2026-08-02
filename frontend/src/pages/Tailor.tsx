import { useNavigate, useParams } from 'react-router-dom'

import { useJob } from '@/hooks/useJobs'
import { Result } from './Result'
import { Run } from './Run'

// The /tailor/:jobId route (T14). The run id lives in the PATH, so a reload or a
// shared link resumes the exact run — the migration invariant from the old
// ?job=… state. Drives Run → Result off the polled job status.
export function Tailor() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const { data: job, isError } = useJob(jobId ?? null)
  const startOver = () => navigate('/')

  if (!jobId || isError) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-28 text-center">
        <p className="font-mono text-xs tracking-[0.34em] text-gap-hi uppercase">off the desk</p>
        <h2 className="mt-4 font-serif text-5xl text-cream">That run isn&rsquo;t here</h2>
        <p className="mx-auto mt-4 max-w-md font-mono text-sm text-cream-soft">
          It may have expired. Start a fresh brief.
        </p>
        <button
          onClick={startOver}
          className="mt-9 h-12 rounded-md border border-cream/25 px-7 font-mono text-sm tracking-[0.2em] text-cream uppercase transition hover:bg-cream/10 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          New brief
        </button>
      </div>
    )
  }

  if (!job) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-32 text-center font-mono text-sm tracking-[0.3em] text-cream-soft uppercase">
        loading the desk…
      </div>
    )
  }

  if (job.status === 'done' && job.result) {
    return (
      <Result
        jobId={job.id}
        round={job.round}
        result={job.result}
        applyUrl={job.apply_url}
        onStartOver={startOver}
      />
    )
  }
  return <Run job={job} onStartOver={startOver} />
}
