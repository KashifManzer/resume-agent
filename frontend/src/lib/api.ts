import type {
  Answer,
  AnswerIn,
  Job,
  JobAnswer,
  JobSummary,
  JdSource,
  Profile,
  ProfileIn,
  ResumeMeta,
} from './types'

/** Error carrying the HTTP status, so callers can branch (e.g. don't retry a 404). */
export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function ok(res: Response): Promise<Response> {
  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    throw new ApiError(detail?.detail ?? `${res.status} ${res.statusText}`, res.status)
  }
  return res
}

/** Run a job from ad-hoc uploads OR library résumé ids (mirrors JD paste-or-link). */
export async function createJob(
  jd: string,
  opts: { files?: File[]; resumeIds?: string[]; applyUrl?: string | null },
): Promise<{ job_id: string }> {
  const form = new FormData()
  form.append('jd', jd)
  for (const f of opts.files ?? []) form.append('files', f, f.name)
  for (const id of opts.resumeIds ?? []) form.append('resume_ids', id)
  if (opts.applyUrl) form.append('apply_url', opts.applyUrl) // T16: link JDs only
  const res = await ok(await fetch('/jobs', { method: 'POST', body: form }))
  return res.json()
}

// --- profile + résumé library (T11) ---------------------------------------

export async function getProfile(): Promise<Profile> {
  return (await ok(await fetch('/profile'))).json()
}

export async function updateProfile(p: ProfileIn): Promise<Profile> {
  const res = await ok(
    await fetch('/profile', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(p),
    }),
  )
  return res.json()
}

export async function listResumes(): Promise<ResumeMeta[]> {
  return (await ok(await fetch('/resumes'))).json()
}

export async function uploadResume(file: File, label?: string): Promise<ResumeMeta> {
  const form = new FormData()
  form.append('file', file, file.name)
  if (label) form.append('label', label)
  return (await ok(await fetch('/resumes', { method: 'POST', body: form }))).json()
}

export async function deleteResume(id: string): Promise<void> {
  await ok(await fetch(`/resumes/${id}`, { method: 'DELETE' }))
}

export async function setDefaultResume(id: string): Promise<ResumeMeta> {
  return (await ok(await fetch(`/resumes/${id}/default`, { method: 'PUT' }))).json()
}

// --- answer bank (T13) ------------------------------------------------------

export async function listAnswers(): Promise<Answer[]> {
  return (await ok(await fetch('/answers'))).json()
}

async function writeAnswer(path: string, method: 'POST' | 'PUT', body: AnswerIn): Promise<Answer> {
  const res = await ok(
    await fetch(path, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  )
  return res.json()
}

export const createAnswer = (body: AnswerIn) => writeAnswer('/answers', 'POST', body)
export const updateAnswer = (id: string, body: AnswerIn) => writeAnswer(`/answers/${id}`, 'PUT', body)

export async function deleteAnswer(id: string): Promise<void> {
  await ok(await fetch(`/answers/${id}`, { method: 'DELETE' }))
}

/** Fetch a JD from a job-posting link; the caller drops `text` into the JD field. */
export async function fetchJdFromUrl(url: string): Promise<JdSource> {
  const res = await ok(
    await fetch('/jd/from-url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    }),
  )
  return res.json()
}

export async function getJob(id: string): Promise<Job> {
  return (await ok(await fetch(`/jobs/${id}`))).json()
}

/** Past runs, newest first (T14 History) — same endpoint the extension picker uses. */
export async function listJobs(): Promise<JobSummary[]> {
  return (await ok(await fetch('/jobs'))).json()
}

export async function sendFeedback(id: string, feedback: string): Promise<{ round: number }> {
  const res = await ok(
    await fetch(`/jobs/${id}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ feedback }),
    }),
  )
  return res.json()
}

/** Draft an answer to an application question, grounded on this run's tailored
 *  résumé (T24). Appends to the run's answers log server-side. */
export async function answerQuestion(id: string, question: string): Promise<JobAnswer> {
  const res = await ok(
    await fetch(`/jobs/${id}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    }),
  )
  return res.json()
}

export const pdfUrl = (id: string) => `/jobs/${id}/pdf`

/** Save the tailored PDF into the repo's tailored-resume/ folder + tracker CSV
 *  (local-dev only). Returns the repo-relative path it wrote. */
export async function saveLocal(id: string): Promise<{ saved_path: string; company: string; position: string }> {
  return (await ok(await fetch(`/jobs/${id}/save-local`, { method: 'POST' }))).json()
}

/** Trigger a client-side download of the final .tex (it's already in the result). */
export function downloadTex(tex: string, filename = 'resume.tex') {
  const url = URL.createObjectURL(new Blob([tex], { type: 'text/x-tex' }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// --- board (T26) -----------------------------------------------------------

import type { BoardFeedOut } from './types'

export async function getBoardFeed(page: number = 1): Promise<BoardFeedOut> {
  const url = `/board?page=${page}`
  return (await ok(await fetch(url))).json()
}

export async function resolveBoardPosting(url: string): Promise<JdSource> {
  return (await ok(await fetch('/board/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  }))).json()
}
