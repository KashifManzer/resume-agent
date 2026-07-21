import { useRef, useState } from 'react'

import { cn } from '@/lib/utils'

export function Dropzone({
  files,
  onChange,
}: {
  files: File[]
  onChange: (files: File[]) => void
}) {
  const [over, setOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  function add(list: FileList | null) {
    if (!list) return
    const merged = [...files]
    for (const f of Array.from(list)) {
      if (f.name.endsWith('.tex') && !merged.some((m) => m.name === f.name)) merged.push(f)
    }
    onChange(merged)
  }

  return (
    <div className="space-y-3">
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload résumé .tex files by clicking or dragging them here"
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            inputRef.current?.click()
          }
        }}
        onDragOver={(e) => {
          e.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setOver(false)
          add(e.dataTransfer.files)
        }}
        className={cn(
          'group flex cursor-pointer flex-col items-center justify-center gap-2 rounded-md border border-dashed border-ink/30 bg-paper/40 px-6 py-10 text-center transition-colors outline-none',
          'hover:border-accent/60 hover:bg-paper-2/60 focus-visible:ring-2 focus-visible:ring-ring',
          over && 'border-accent bg-paper-2 ring-2 ring-accent/40',
        )}
      >
        <span className="font-mono text-xs tracking-widest text-ink-soft uppercase">
          drop &middot; browse
        </span>
        <span className="font-serif text-lg text-ink">Add your résumé sources</span>
        <span className="text-sm text-ink-soft">
          One or more <code className="font-mono text-accent">.tex</code> files — we&rsquo;ll pick the
          closest to the job.
        </span>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".tex"
        multiple
        className="hidden"
        onChange={(e) => {
          add(e.target.files)
          e.target.value = ''
        }}
      />

      {files.length > 0 && (
        <ul className="divide-y divide-border rounded-md border border-border bg-paper-2/70">
          {files.map((f) => (
            <li key={f.name} className="flex items-center justify-between gap-3 px-4 py-2.5">
              <span className="flex min-w-0 items-center gap-2">
                <span aria-hidden className="text-accent">
                  §
                </span>
                <span className="truncate font-mono text-sm text-ink">{f.name}</span>
                <span className="shrink-0 font-mono text-xs text-ink-soft">
                  {(f.size / 1024).toFixed(1)} kb
                </span>
              </span>
              <button
                type="button"
                onClick={() => onChange(files.filter((x) => x.name !== f.name))}
                aria-label={`Remove ${f.name}`}
                className="rounded px-2 py-1 font-mono text-xs text-ink-soft transition-colors hover:text-gap focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
