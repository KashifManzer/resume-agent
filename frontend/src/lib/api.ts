import type { Job, JdSource, Profile, ProfileIn, ResumeMeta } from './types'

async function ok(res: Response): Promise<Response> {
  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    throw new Error(detail?.detail ?? `${res.status} ${res.statusText}`)
  }
  return res
}

/** Run a job from ad-hoc uploads OR library résumé ids (mirrors JD paste-or-link). */
export async function createJob(
  jd: string,
  opts: { files?: File[]; resumeIds?: string[] },
): Promise<{ job_id: string }> {
  const form = new FormData()
  form.append('jd', jd)
  for (const f of opts.files ?? []) form.append('files', f, f.name)
  for (const id of opts.resumeIds ?? []) form.append('resume_ids', id)
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

export const pdfUrl = (id: string) => `/jobs/${id}/pdf`

/** Trigger a client-side download of the final .tex (it's already in the result). */
export function downloadTex(tex: string, filename = 'resume.tex') {
  const url = URL.createObjectURL(new Blob([tex], { type: 'text/x-tex' }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
