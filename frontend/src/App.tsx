import { useState } from 'react'

import { useJob } from './hooks/useJobs'
import { Compose } from './pages/Compose'
import { Result } from './pages/Result'
import { Run } from './pages/Run'

function Masthead() {
  return (
    <header className="border-b border-ink/15">
      <div className="mx-auto flex max-w-6xl items-baseline justify-between px-6 py-4">
        <span className="font-serif text-xl tracking-tight text-ink">
          Résumé<span className="text-accent">·</span>Proof
        </span>
        <span className="font-mono text-[10px] tracking-[0.3em] text-ink-soft uppercase">
          tailored · honest · one page
        </span>
      </div>
    </header>
  )
}

function Loading() {
  return (
    <div className="mx-auto max-w-2xl px-6 py-32 text-center font-mono text-sm tracking-widest text-ink-soft uppercase">
      loading the desk…
    </div>
  )
}

export default function App() {
  const [jobId, setJobId] = useState<string | null>(null)
  const { data: job } = useJob(jobId)
  const reset = () => setJobId(null)

  return (
    <div className="min-h-svh">
      <Masthead />
      {!jobId ? (
        <Compose onCreated={setJobId} />
      ) : !job ? (
        <Loading />
      ) : job.status === 'done' && job.result ? (
        <Result jobId={job.id} round={job.round} result={job.result} onStartOver={reset} />
      ) : (
        <Run job={job} onStartOver={reset} />
      )}
    </div>
  )
}
