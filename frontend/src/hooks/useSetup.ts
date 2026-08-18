import { useExtensionInstalled } from '@/hooks/useExtension'
import { useJobsList } from '@/hooks/useJobs'
import { useProfile, useResumes } from '@/hooks/useProfile'

const TAILORED_KEY = 'has-tailored'

/** Remember that a run was started. The job list itself is in-memory on the
 *  backend, so it empties on every restart — without this, a set-up user would
 *  fall back to the first-run intro each time the server bounced. */
export const markTailored = () => localStorage.setItem(TAILORED_KEY, '1')

/** The four setup signals, in Onboarding's checklist order — `null` while they
 *  are still loading, so nothing gated on "first run" flashes on a cold render.
 *  One source of truth: the checklist renders them step by step, Home() rolls
 *  them up to decide whether this is a first run. */
export function useSetupProgress(): boolean[] | null {
  const profile = useProfile()
  const resumes = useResumes()
  const jobs = useJobsList()
  const extension = useExtensionInstalled()
  if (profile.isPending || resumes.isPending || jobs.isPending) return null
  return [
    Boolean(profile.data?.name || profile.data?.email),
    (resumes.data?.length ?? 0) > 0,
    extension,
    (jobs.data?.length ?? 0) > 0 || localStorage.getItem(TAILORED_KEY) === '1',
  ]
}
