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
    <section className="sheet p-7">
      <header className="flex items-baseline justify-between">
        <h3 className="font-serif text-2xl text-ink">Ask for a revision</h3>
        <span className="font-mono text-[11px] tracking-[0.15em] text-ink-soft uppercase">
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
            className="mt-4 min-h-24 resize-y border-ink/20 bg-paper text-ink focus-visible:ring-marigold"
          />
          {feedback.isError && (
            <p role="alert" className="mt-2 font-mono text-sm text-gap">
              {(feedback.error as Error).message}
            </p>
          )}
          <Button
            onClick={() => feedback.mutate(text, { onSuccess: () => setText('') })}
            disabled={text.trim().length < 4 || feedback.isPending}
            className="mt-4 h-11 rounded-md bg-marigold px-6 font-mono text-sm tracking-[0.18em] text-ink uppercase transition hover:brightness-95 disabled:opacity-40"
          >
            {feedback.isPending ? 'sending…' : 'Revise'}
          </Button>
        </>
      )}
    </section>
  )
}
