import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  ApiError,
  createJob,
  fetchJdFromUrl,
  getJob,
  listJobs,
  saveLocal,
  sendFeedback,
} from '@/lib/api'
import type { Job } from '@/lib/types'

export function useCreateJob() {
  return useMutation({
    mutationFn: ({
      jd,
      files,
      resumeIds,
      applyUrl,
    }: {
      jd: string
      files?: File[]
      resumeIds?: string[]
      applyUrl?: string | null
    }) => createJob(jd, { files, resumeIds, applyUrl }),
  })
}

/** Fetch a JD from a job link (T10). Caller fills the editable JD field on success. */
export function useJdFromUrl() {
  return useMutation({ mutationFn: (url: string) => fetchJdFromUrl(url) })
}

/** All past runs for the History section (T14). */
export function useJobsList() {
  return useQuery({ queryKey: ['jobs'], queryFn: listJobs })
}

/** Save the tailored PDF into the repo folder + tracker CSV (local-dev only). */
export function useSaveLocal() {
  return useMutation({ mutationFn: (id: string) => saveLocal(id) })
}

/** Poll a job every 2s until it finishes (long jobs — minutes). */
export function useJob(id: string | null) {
  return useQuery({
    queryKey: ['job', id],
    queryFn: () => getJob(id!),
    enabled: !!id,
    // A missing/expired id (404) is terminal — don't retry it, so the query
    // settles to error fast and /tailor/:jobId shows its not-found state instead
    // of polling forever (T14). Transient errors still get a few retries.
    retry: (n, err) => !(err instanceof ApiError && err.status === 404) && n < 3,
    refetchInterval: (q) => {
      if (q.state.status === 'error') return false // stop on a gone/failed job
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
