import { useState } from 'react'

import { useJob } from './hooks/useJobs'
import { Compose } from './pages/Compose'
import { Profile } from './pages/Profile'
import { Result } from './pages/Result'
import { Run } from './pages/Run'

type View = 'compose' | 'profile'

function Masthead({ view, onNav }: { view: View | null; onNav: (v: View) => void }) {
  const link = (v: View, text: string) => (
    <button
      onClick={() => onNav(v)}
      className={`font-mono text-[10px] tracking-[0.32em] uppercase transition-colors hover:text-marigold ${
        view === v ? 'text-marigold' : 'text-cream-soft'
      }`}
    >
      {text}
    </button>
  )
  return (
    <header className="relative">
      <div className="mx-auto max-w-6xl px-6">
        <div className="border-t border-desk-line pt-3 font-mono text-[10px] tracking-[0.32em] text-cream-soft uppercase">
          Est. on the desk
        </div>
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 pb-3">
          <span className="font-serif text-2xl font-medium tracking-tight text-cream">
            Résumé<span className="text-marigold">·</span>Proof
          </span>
          <nav className="flex items-center gap-5">
            {link('compose', 'the desk')}
            {link('profile', 'profile')}
          </nav>
        </div>
      </div>
      {/* the masthead's double rule — thick marigold over a hairline */}
      <div className="h-[3px] bg-marigold" />
      <div className="h-px bg-desk-line" />
    </header>
  )
}

function Loading() {
  return (
    <div className="mx-auto max-w-2xl px-6 py-32 text-center font-mono text-sm tracking-[0.3em] text-cream-soft uppercase">
      loading the desk…
    </div>
  )
}

function setJobParam(id: string | null) {
  const url = new URL(window.location.href)
  if (id) url.searchParams.set('job', id)
  else url.searchParams.delete('job')
  window.history.replaceState({}, '', url)
}

export default function App() {
  // resumable: a job id in the URL (?job=…) survives reloads and is shareable
  const [jobId, setJobId] = useState<string | null>(
    () => new URLSearchParams(window.location.search).get('job'),
  )
  const [view, setView] = useState<View>('compose')
  const { data: job } = useJob(jobId)
  const start = (id: string) => {
    setJobId(id)
    setJobParam(id)
  }
  const reset = () => {
    setJobId(null)
    setJobParam(null)
  }
  // masthead nav leaves any active job and switches the desk/profile view
  const nav = (v: View) => {
    reset()
    setView(v)
  }

  return (
    <div className="min-h-svh overflow-x-clip">
      <Masthead view={jobId ? null : view} onNav={nav} />
      {jobId ? (
        !job ? (
          <Loading />
        ) : job.status === 'done' && job.result ? (
          <Result jobId={job.id} round={job.round} result={job.result} onStartOver={reset} />
        ) : (
          <Run job={job} onStartOver={reset} />
        )
      ) : view === 'profile' ? (
        <Profile onBack={() => setView('compose')} />
      ) : (
        <Compose onCreated={start} />
      )}
    </div>
  )
}
