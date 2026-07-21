export function KeywordMarks({ matched, missing }: { matched: string[]; missing: string[] }) {
  return (
    <div className="space-y-4">
      <div>
        <div className="mb-2 font-mono text-[11px] tracking-[0.2em] text-ink-soft uppercase">
          covered &middot; {matched.length}
        </div>
        <div className="flex flex-wrap gap-x-1.5 gap-y-2 font-serif text-lg leading-relaxed">
          {matched.length === 0 && <span className="text-sm text-ink-soft">—</span>}
          {matched.map((k, i) => (
            <span key={k} className="mark-hl" style={{ animationDelay: `${0.5 + i * 0.05}s` }}>
              {k}
            </span>
          ))}
        </div>
      </div>

      {missing.length > 0 && (
        <div>
          <div className="mb-2 font-mono text-[11px] tracking-[0.2em] text-gap uppercase">
            gaps &middot; {missing.length}
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-1 font-serif text-lg">
            {missing.map((k) => (
              <span key={k} className="mark-gap">
                {k}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
