import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { createJob, fetchJdFromUrl, getJob, sendFeedback } from '@/lib/api'
import type { Job } from '@/lib/types'

export function useCreateJob() {
  return useMutation({
    mutationFn: ({ jd, files, resumeIds }: { jd: string; files?: File[]; resumeIds?: string[] }) =>
      createJob(jd, { files, resumeIds }),
  })
}

/** Fetch a JD from a job link (T10). Caller fills the editable JD field on success. */
export function useJdFromUrl() {
  return useMutation({ mutationFn: (url: string) => fetchJdFromUrl(url) })
}

/** Poll a job every 2s until it finishes (long jobs — minutes). */
export function useJob(id: string | null) {
  return useQuery({
    queryKey: ['job', id],
    queryFn: () => getJob(id!),
    enabled: !!id,
    refetchInterval: (q) => {
      const s = (q.state.data as Job | undefined)?.status
      return s === 'done' || s === 'error' ? false : 2000
    },
  })
}

export function useFeedback(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (feedback: string) => sendFeedback(id, feedback),
    // a new round is queued server-side; resume polling immediately
    onSuccess: () => qc.invalidateQueries({ queryKey: ['job', id] }),
  })
}
