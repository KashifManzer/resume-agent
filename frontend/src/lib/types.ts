// Mirrors the backend schemas (T3/T5/T6).

export interface AtsScore {
  overall: number
  keyword_coverage: number
  llm_fit: number
  required_keywords: string[]
  matched: string[]
  missing: string[]
  rationale: string
}

export interface HiringAgentReport {
  overall: number
  categories: Record<string, number>
  advice: string[]
  note: string
}

export interface Report {
  selection_warning: string | null
  ats_before: AtsScore
  ats_after: AtsScore
  changes: string[]
  added: string[]
  hiring_agent: HiringAgentReport | null
  warnings: string[]
}

export interface PipelineResult {
  pdf_path: string
  tex: string
  report: Report
}

export interface Links {
  github: string | null
  linkedin: string | null
  portfolio: string | null
}

export interface Profile {
  id: string
  name: string | null
  email: string | null
  phone: string | null
  location: string | null
  work_auth: string | null
  // T17 — assisted screening self-ID (all voluntary; "yes"/"no"/"decline" for the pickers)
  work_eligible: string | null
  needs_sponsorship: string | null
  gender: string | null
  race: string | null
  disability: string | null
  veteran: string | null
  links: Links
}

export type ProfileIn = Omit<Profile, 'id'>

export interface ResumeMeta {
  id: string
  label: string | null
  format: string
  filename: string | null
  is_default: boolean
  created_at: string
}

export interface JdSource {
  text: string
  title: string | null
  location: string | null
  company: string | null
  source_url: string
  apply_url: string | null // T16: the ATS apply form (null for pasted/generic JDs)
  adapter: string
  warnings: string[]
}

// Answer bank (T13). Seeded canonical-core rows carry `canonical` (question
// null); custom rows carry `question` (canonical null).
export type AnswerMode = 'verbatim' | 'adaptable'

export interface Answer {
  id: string
  canonical: string | null
  question: string | null
  answer: string
  mode: string
}

export interface AnswerIn {
  question?: string | null
  answer: string
  mode: AnswerMode
}

export type JobStatus = 'queued' | 'running' | 'done' | 'error'

// Lightweight run row for the History list (GET /jobs) — no result payload.
export interface JobSummary {
  id: string
  title: string
  status: JobStatus
  created_at: string
  has_pdf: boolean
}

export interface Job {
  id: string
  status: JobStatus
  progress: string[]
  result: PipelineResult | null
  error: string | null
  round: number
  apply_url: string | null // T16: the ATS apply form, when the JD came from a link
}

export const OUTER_LOOP_MAX = 5
