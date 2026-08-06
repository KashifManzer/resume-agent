import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes, useSearchParams } from 'react-router-dom'

import { AppShell } from './AppShell'
import { Onboarding } from './components/Onboarding'
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

// Home = onboarding checklist + the Compose brief. Preserves the pre-router
// reload-resume link: an old ?job=… lands you back on that run's /tailor route.
function Home() {
  const [params] = useSearchParams()
  const legacy = params.get('job')
  if (legacy) return <Navigate to={`/tailor/${legacy}`} replace />
  return (
    <>
      <Onboarding />
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
