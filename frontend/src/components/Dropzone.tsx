import { useRef, useState } from 'react'

import { cn } from '@/lib/utils'

export function Dropzone({
  files,
  onChange,
  title = 'Add your résumé sources',
  hint,
}: {
  files: File[]
  onChange: (files: File[]) => void
  title?: string
  hint?: React.ReactNode
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
          'sheet group relative flex cursor-pointer flex-col items-center justify-center gap-2 px-6 py-12 text-center transition-all outline-none',
          'hover:-translate-y-0.5 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-desk',
          over && 'ring-2 ring-marigold',
        )}
      >
        {/* dashed proofing border, inset from the sheet edge */}
        <span
          aria-hidden
          className={cn(
            'pointer-events-none absolute inset-2.5 rounded-sm border border-dashed transition-colors',
            over ? 'border-marigold' : 'border-ink/25 group-hover:border-accent/60',
          )}
        />
        <span className="font-mono text-[11px] tracking-[0.28em] text-ink-soft uppercase">
          drop &middot; browse
        </span>
        <span className="font-serif text-2xl text-ink">{title}</span>
        <span className="text-sm text-ink-soft">
          {hint ?? (
            <>
              One or more <code className="font-mono text-accent">.tex</code> files — we&rsquo;ll pick
              the closest to the job.
            </>
          )}
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
        <ul className="sheet-sm divide-y divide-border overflow-hidden">
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
