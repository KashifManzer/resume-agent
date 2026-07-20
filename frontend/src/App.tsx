import { useEffect, useState } from 'react'

function App() {
  const [health, setHealth] = useState('checking…')

  useEffect(() => {
    fetch('/health')
      .then((r) => r.json())
      .then((d) => setHealth(d.status ?? 'unknown'))
      .catch(() => setHealth('unreachable'))
  }, [])

  return (
    <main style={{ fontFamily: 'system-ui', padding: '2rem' }}>
      <h1>Resume Agent</h1>
      <p>
        backend /health: <strong>{health}</strong>
      </p>
    </main>
  )
}

export default App
