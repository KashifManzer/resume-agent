import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes, useSearchParams } from 'react-router-dom'

import { AppShell } from './AppShell'
import { Guarantees } from './components/Guarantees'
import { Onboarding } from './components/Onboarding'
import { useSetupProgress } from './hooks/useSetup'
import { Answers } from './pages/Answers'
import { Compose } from './pages/Compose'
import { History } from './pages/History'
import { Library } from './pages/Library'
import { Profile } from './pages/Profile'
import { Tailor } from './pages/Tailor'

// Dev-only component gallery. The `import.meta.env.DEV ? … : null` is a compile-time
// constant, so the whole branch (and the Gallery chunk) is dead-code-eliminated
// from the prod build — never in the bundle, never in the nav.
const Gallery = import.meta.env.DEV ? lazy(() => import('./pages/dev/Gallery')) : null

// Home = the first-run intro (checklist + trust band) above the Compose brief.
// Both intro pieces hang off the same signal: while setup is incomplete this is
// a taller, naturally-scrolling orientation page; once it's done they're gone and
// Compose is a viewport-locked working screen (T21). Preserves the pre-router
// reload-resume link: an old ?job=… lands you back on that run's /tailor route.
function Home() {
  const [params] = useSearchParams()
  const setup = useSetupProgress()
  const firstRun = setup !== null && setup.some((done) => !done)
  const legacy = params.get('job')
  if (legacy) return <Navigate to={`/tailor/${legacy}`} replace />
  return (
    <>
      <Onboarding />
      {firstRun && <Guarantees />}
      <Compose />
    </>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Home />} />
        <Route path="/tailor/:jobId" element={<Tailor />} />
        <Route path="/library" element={<Library />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/answers" element={<Answers />} />
        <Route path="/history" element={<History />} />
        {Gallery && (
          <Route
            path="/dev/gallery"
            element={
              <Suspense fallback={null}>
                <Gallery />
              </Suspense>
            }
          />
        )}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
