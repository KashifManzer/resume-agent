import { useNavigate, useParams } from 'react-router-dom'

import { ErrorState } from '@/components/states/ErrorState'
import { Loading } from '@/components/states/Loading'
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
      <ErrorState
        kicker="off the desk"
        title={<>That run isn&rsquo;t here</>}
        action={{ label: 'New brief', onClick: startOver }}
      >
        It may have expired. Start a fresh brief.
      </ErrorState>
    )
  }

  if (!job) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-32 text-center">
        <Loading className="tracking-[0.3em]">loading the desk…</Loading>
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
