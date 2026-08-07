import { useState } from 'react'
import { motion } from 'motion/react'
import { Link } from 'react-router-dom'

import { Dropzone } from '@/components/Dropzone'
import { EmptyState } from '@/components/states/EmptyState'
import { InlineError } from '@/components/states/InlineError'
import { ListSkeleton } from '@/components/states/ListSkeleton'
import { Button } from '@/components/ui/button'
import { SectionHeading } from '@/components/ui/SectionHeading'
import { Sheet } from '@/components/ui/Sheet'
import {
  useDeleteResume,
  useResumes,
  useSetDefaultResume,
  useUploadResume,
} from '@/hooks/useProfile'
import { rise, stagger, useEntrance } from '@/lib/motion'

// Résumé library (T14 — split out of the old combined Profile page). Save your
// .tex sources once; every run picks from them without a re-upload.
export function Library() {
  const { data: resumes, isPending, isError, refetch } = useResumes()
  const upload = useUploadResume()
  const del = useDeleteResume()
  const setDefault = useSetDefaultResume()
  const [staged, setStaged] = useState<File[]>([])
  const entrance = useEntrance()

  async function addResumes() {
    if (!staged.length) return
    for (const file of staged) await upload.mutateAsync({ file })
    setStaged([])
  }

  return (
    <motion.div
      variants={stagger}
      {...entrance}
      className="mx-auto max-w-4xl space-y-10 px-6 py-16 lg:py-20"
    >
      <motion.div variants={rise}>
        <SectionHeading kicker="set up & track · résumé library" title={<>Your sources<span className="text-marigold">.</span></>}>
          Lay your <code className="font-mono text-cream">.tex</code> résumés on the desk once. The
          tailor picks the closest to each job — no re-upload, ever.
        </SectionHeading>
      </motion.div>

      <motion.div variants={rise}>
      {isPending ? (
        <ListSkeleton />
      ) : isError ? (
        <InlineError onRetry={() => refetch()}>
          Couldn&rsquo;t load your library — is the backend running?
        </InlineError>
      ) : resumes && resumes.length > 0 ? (
        <Sheet as="ul" sm className="divide-y divide-border overflow-hidden">
          {resumes.map((r) => (
            <li key={r.id} className="flex items-center justify-between gap-3 px-4 py-3">
              <span className="flex min-w-0 items-center gap-3">
                <span aria-hidden className="text-accent">§</span>
                <span className="truncate font-mono text-sm text-ink">{r.label || r.filename}</span>
                {r.is_default && (
                  <span className="shrink-0 rounded bg-marigold/20 px-2 py-0.5 font-mono text-[10px] tracking-[0.15em] text-marigold uppercase">
                    default
                  </span>
                )}
              </span>
              <span className="flex shrink-0 items-center gap-1">
                {!r.is_default && (
                  <button
                    onClick={() => setDefault.mutate(r.id)}
                    className="rounded px-2 py-1 font-mono text-xs text-ink-soft hover:text-accent"
                  >
                    make default
                  </button>
                )}
                <button
                  onClick={() => del.mutate(r.id)}
                  aria-label={`Delete ${r.label || r.filename}`}
                  className="rounded px-2 py-1 font-mono text-xs text-ink-soft hover:text-gap"
                >
                  remove
                </button>
              </span>
            </li>
          ))}
        </Sheet>
      ) : (
        <EmptyState title="An empty desk.">
          Add your first <code className="font-mono text-accent">.tex</code> résumé below — then{' '}
          <Link to="/" className="text-accent underline-offset-2 hover:underline">
            tailor it to a job
          </Link>
          .
        </EmptyState>
      )}
      </motion.div>

      <motion.div variants={rise}>
        <Dropzone
          files={staged}
          onChange={setStaged}
          title="Add résumés to your library"
          hint={
            <>
              Drop one or more <code className="font-mono text-accent">.tex</code> files — reuse them
              on any run, no re-upload.
            </>
          }
        />
      </motion.div>
      <motion.div variants={rise} className="flex items-center gap-4">
        <Button
          onClick={addResumes}
          disabled={!staged.length || upload.isPending}
          className="h-11 rounded-md bg-cream-soft/10 px-5 font-mono text-xs tracking-[0.15em] text-cream uppercase transition hover:bg-cream-soft/20 disabled:opacity-40"
        >
          {upload.isPending ? 'adding…' : `Add ${staged.length ? `${staged.length} ` : ''}to library`}
        </Button>
        {upload.isError && (
          <p role="alert" className="font-mono text-xs text-gap-hi">
            {(upload.error as Error).message}
          </p>
        )}
      </motion.div>
    </motion.div>
  )
}
