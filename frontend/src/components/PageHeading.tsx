// Shared masthead for the "set up & track" sections (T14) — keeps Library,
// Profile, Answers and History speaking the same proofing-desk voice.
export function PageHeading({
  kicker,
  title,
  children,
}: {
  kicker: string
  title: React.ReactNode
  children?: React.ReactNode
}) {
  return (
    <header className="space-y-3">
      <p className="font-mono text-xs tracking-[0.34em] text-marigold uppercase">{kicker}</p>
      <h1 className="font-serif text-5xl font-medium tracking-[-0.02em] text-cream sm:text-6xl">
        {title}
      </h1>
      {children && <p className="max-w-xl leading-relaxed text-cream-soft">{children}</p>}
    </header>
  )
}
