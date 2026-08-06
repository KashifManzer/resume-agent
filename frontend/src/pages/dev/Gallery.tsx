import { EmptyState } from '@/components/states/EmptyState'
import { ErrorState } from '@/components/states/ErrorState'
import { InlineError } from '@/components/states/InlineError'
import { ListSkeleton } from '@/components/states/ListSkeleton'
import { Loading } from '@/components/states/Loading'
import { Kicker } from '@/components/ui/Kicker'
import { Mark } from '@/components/ui/Mark'
import { SectionHeading } from '@/components/ui/SectionHeading'
import { Sheet } from '@/components/ui/Sheet'
import { Skeleton } from '@/components/ui/Skeleton'
import { Stamp } from '@/components/ui/Stamp'

// Dev-only component gallery (mounted only when import.meta.env.DEV — see App.tsx,
// never in the nav or the prod bundle). One place to see + work the whole
// proofing-desk vocabulary. No Storybook: a route is lazier and adds no dep.
function Spec({ name, children }: { name: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="font-mono text-[11px] tracking-[0.26em] text-cream-soft uppercase">{name}</h2>
      {children}
    </section>
  )
}

export default function Gallery() {
  return (
    <div className="mx-auto max-w-4xl space-y-12 px-6 py-16">
      <SectionHeading kicker="dev · gallery" title={<>The vocabulary<span className="text-marigold">.</span></>}>
        Every primitive and page-state in one place. Dev-only — not in the nav, not in prod.
      </SectionHeading>

      <Spec name="Kicker">
        <Kicker>the proofing desk</Kicker>
        <Kicker tone="gap">the press jammed</Kicker>
      </Spec>

      <Spec name="SectionHeading">
        <SectionHeading kicker="set up & track · example" title={<>Your details<span className="text-marigold">.</span></>}>
          The masthead used across the track pages.
        </SectionHeading>
      </Spec>

      <Spec name="Sheet">
        <Sheet className="p-7">
          <p className="text-ink">A sheet of warm paper on the desk.</p>
        </Sheet>
      </Spec>

      <Spec name="Sheet · sm (list)">
        <Sheet as="ul" sm className="divide-y divide-border overflow-hidden">
          {['resume-swe.tex', 'resume-ml.tex'].map((f) => (
            <li key={f} className="px-4 py-2.5 font-mono text-sm text-ink">{f}</li>
          ))}
        </Sheet>
      </Spec>

      <Spec name="Mark">
        <div className="flex flex-wrap gap-x-2 gap-y-2.5 text-lg">
          <Mark>Kubernetes</Mark>
          <Mark>Terraform</Mark>
          <Mark kind="gap">Rust</Mark>
        </div>
      </Spec>

      <Spec name="Stamp">
        <div className="relative h-28">
          <Stamp className="absolute top-4 left-8" sub={<>one page · {new Date().getFullYear()}</>} />
        </div>
      </Spec>

      <Spec name="EmptyState">
        <EmptyState title="An empty desk.">
          Add your first source below — then tailor it to a job.
        </EmptyState>
      </Spec>

      <Spec name="Loading">
        <Loading>loading the desk…</Loading>
      </Spec>

      <Spec name="Skeleton">
        <div className="max-w-sm space-y-2">
          <Skeleton className="h-3.5 w-2/3" />
          <Skeleton className="h-3.5 w-1/2" />
        </div>
      </Spec>

      <Spec name="ListSkeleton (paper loading)">
        <ListSkeleton rows={3} />
      </Spec>

      <Spec name="InlineError (recoverable)">
        <InlineError onRetry={() => {}}>Couldn&rsquo;t load this — is the backend running?</InlineError>
      </Spec>

      <Spec name="ErrorState">
        <ErrorState kicker="off the desk" title="That run isn't here" action={{ label: 'New brief', onClick: () => {} }}>
          It may have expired. Start a fresh brief.
        </ErrorState>
      </Spec>
    </div>
  )
}
