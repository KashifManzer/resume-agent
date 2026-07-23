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
  adapter: string
  warnings: string[]
}

export type JobStatus = 'queued' | 'running' | 'done' | 'error'

export interface Job {
  id: string
  status: JobStatus
  progress: string[]
  result: PipelineResult | null
  error: string | null
  round: number
}

export const OUTER_LOOP_MAX = 5
