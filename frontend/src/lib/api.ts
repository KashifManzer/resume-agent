import type { Job, JdSource } from './types'

async function ok(res: Response): Promise<Response> {
  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    throw new Error(detail?.detail ?? `${res.status} ${res.statusText}`)
  }
  return res
}

export async function createJob(jd: string, files: File[]): Promise<{ job_id: string }> {
  const form = new FormData()
  form.append('jd', jd)
  for (const f of files) form.append('files', f, f.name)
  const res = await ok(await fetch('/jobs', { method: 'POST', body: form }))
  return res.json()
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
