import { NavLink, Outlet } from 'react-router-dom'

import { useExtensionInstalled } from '@/hooks/useExtension'

// The desk organizer's index tabs (T14). Two zones — "do" (Tailor) and "set up
// & track" (the rest) — read as lettered dividers in a card index. NavLink sets
// aria-current="page", which the .idx-tab styles turn into the pulled-forward
// cream tab with a marigold ink-mark.
const TABS = [
  { to: '/', letter: 'A', label: 'Tailor', zone: 'do', end: true },
  { to: '/library', letter: 'B', label: 'Library', zone: 'set up & track' },
  { to: '/profile', letter: 'C', label: 'Profile', zone: 'set up & track' },
  { to: '/answers', letter: 'D', label: 'Answers', zone: 'set up & track' },
  { to: '/history', letter: 'E', label: 'History', zone: 'set up & track' },
] as const

function ZoneCaption({ children }: { children: React.ReactNode }) {
  return (
    <span
      aria-hidden
      className="hidden shrink-0 self-end pb-2 pl-1 font-mono text-[9px] tracking-[0.26em] text-cream-soft/55 uppercase sm:inline"
    >
      {children}
    </span>
  )
}

function ExtensionPill() {
  const installed = useExtensionInstalled()
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[10px] tracking-[0.18em] uppercase ${
        installed
          ? 'border-marigold/40 text-marigold'
          : 'border-cream-soft/25 text-cream-soft'
      }`}
      title={installed ? 'The autofill extension is installed' : 'The autofill extension is not detected'}
    >
      <span
        aria-hidden
        className={`h-1.5 w-1.5 rounded-full ${installed ? 'bg-marigold' : 'bg-cream-soft/50'}`}
      />
      {installed ? 'extension on' : 'no extension'}
    </span>
  )
}

export function AppShell() {
  return (
    <div className="min-h-svh overflow-x-clip">
      <header className="relative">
        <div className="mx-auto max-w-6xl px-6">
          <div className="flex items-center justify-between border-t border-desk-line pt-3">
            <span className="font-mono text-[10px] tracking-[0.32em] text-cream-soft uppercase">
              Est. on the desk
            </span>
            <ExtensionPill />
          </div>

          <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 pt-2 pb-3">
            <NavLink to="/" className="font-serif text-2xl font-medium tracking-tight text-cream">
              Résumé<span className="text-marigold">·</span>Proof
            </NavLink>
          </div>

          {/* the index-tab rail — the tabs stand on the marigold desk edge below */}
          <nav aria-label="Sections" className="tab-rail -mb-px flex items-end gap-1 overflow-x-auto">
            <ZoneCaption>do</ZoneCaption>
            {TABS.filter((t) => t.zone === 'do').map((t) => (
              <Tab key={t.to} {...t} />
            ))}
            <span aria-hidden className="mx-1 h-6 w-px shrink-0 self-end bg-desk-line" />
            <ZoneCaption>set up &amp; track</ZoneCaption>
            {TABS.filter((t) => t.zone === 'set up & track').map((t) => (
              <Tab key={t.to} {...t} />
            ))}
          </nav>
        </div>
        <div className="h-[3px] bg-marigold" />
        <div className="h-px bg-desk-line" />
      </header>

      <main>
        <Outlet />
      </main>
    </div>
  )
}

function Tab({ to, letter, label, end }: { to: string; letter: string; label: string; end?: boolean }) {
  return (
    <NavLink to={to} end={end} className="idx-tab">
      <span className="idx-kicker">{letter}</span>
      <span className="idx-label">{label}</span>
    </NavLink>
  )
}
