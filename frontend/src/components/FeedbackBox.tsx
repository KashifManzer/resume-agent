import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { useFeedback } from '@/hooks/useJobs'
import { OUTER_LOOP_MAX } from '@/lib/types'

export function FeedbackBox({ jobId, round }: { jobId: string; round: number }) {
  const [text, setText] = useState('')
  const feedback = useFeedback(jobId)
  const left = OUTER_LOOP_MAX - round
  const atCap = left <= 0

  return (
    <section className="rounded-lg border border-border bg-paper-2/80 p-6">
      <header className="flex items-baseline justify-between">
        <h3 className="font-serif text-xl text-ink">Ask for a revision</h3>
        <span className="font-mono text-xs text-ink-soft">
          {atCap ? 'no rounds left' : `${left} round${left === 1 ? '' : 's'} left`}
        </span>
      </header>

      {atCap ? (
        <p className="mt-3 font-mono text-sm text-ink-soft">
          You&rsquo;ve used all {OUTER_LOOP_MAX} revision rounds. Start over for a fresh run.
        </p>
      ) : (
        <>
          <label htmlFor="feedback" className="sr-only">
            Revision request
          </label>
          <Textarea
            id="feedback"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="e.g. lead with the platform work; tone down the AI/ML framing…"
            className="mt-3 min-h-24 resize-y border-ink/20 bg-paper/60 font-serif text-ink focus-visible:ring-accent"
          />
          {feedback.isError && (
            <p role="alert" className="mt-2 font-mono text-sm text-gap">
              {(feedback.error as Error).message}
            </p>
          )}
          <Button
            onClick={() => feedback.mutate(text, { onSuccess: () => setText('') })}
            disabled={text.trim().length < 4 || feedback.isPending}
            className="mt-3 h-11 rounded-md bg-ink px-5 font-mono text-sm tracking-widest text-primary-foreground uppercase hover:bg-ink/90 disabled:opacity-40"
          >
            {feedback.isPending ? 'sending…' : 'Revise'}
          </Button>
        </>
      )}
    </section>
  )
}
