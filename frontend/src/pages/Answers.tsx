import { AnswerBank } from '@/components/AnswerBank'
import { SectionHeading } from '@/components/ui/SectionHeading'

// Answer bank (T14 — split out of the old combined Profile page). Reusable
// screening answers the extension fills, and drafts from when left blank.
export function Answers() {
  return (
    <div className="mx-auto max-w-4xl space-y-8 px-6 py-16 lg:py-20">
      <SectionHeading kicker="set up & track · answer bank" title={<>Your answers<span className="text-marigold">.</span></>}>
        Reusable screening answers. <span className="text-cream">Verbatim</span> facts fill as-is;{' '}
        <span className="text-cream">adaptable</span> templates get tailored to each job. The
        extension drafts anything you leave blank — you always review before submitting.
      </SectionHeading>
      <AnswerBank />
    </div>
  )
}
