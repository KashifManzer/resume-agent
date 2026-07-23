import { useEffect, useState } from 'react'

import { Dropzone } from '@/components/Dropzone'
import { Button } from '@/components/ui/button'
import {
  useDeleteResume,
  useProfile,
  useResumes,
  useSetDefaultResume,
  useUpdateProfile,
  useUploadResume,
} from '@/hooks/useProfile'
import type { ProfileIn } from '@/lib/types'

const EMPTY: ProfileIn = {
  name: '',
  email: '',
  phone: '',
  location: '',
  work_auth: '',
  links: { github: '', linkedin: '', portfolio: '' },
}

const inputCls =
  'w-full rounded-md border border-cream-soft/20 bg-transparent px-3 py-2.5 font-mono text-sm text-cream placeholder:text-cream-soft/40 focus:border-marigold focus:outline-none'

function Field({ label, ...props }: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="block space-y-1.5">
      <span className="font-mono text-[10px] tracking-[0.22em] text-cream-soft uppercase">{label}</span>
      <input className={inputCls} {...props} />
    </label>
  )
}

export function Profile({ onBack }: { onBack: () => void }) {
  const { data: profile } = useProfile()
  const { data: resumes = [] } = useResumes()
  const save = useUpdateProfile()
  const upload = useUploadResume()
  const del = useDeleteResume()
  const setDefault = useSetDefaultResume()

  const [form, setForm] = useState<ProfileIn>(EMPTY)
  const [staged, setStaged] = useState<File[]>([]) // files queued for upload

  // hydrate the form once the profile loads (null fields → empty strings)
  useEffect(() => {
    if (profile)
      setForm({
        name: profile.name ?? '',
        email: profile.email ?? '',
        phone: profile.phone ?? '',
        location: profile.location ?? '',
        work_auth: profile.work_auth ?? '',
        links: {
          github: profile.links?.github ?? '',
          linkedin: profile.links?.linkedin ?? '',
          portfolio: profile.links?.portfolio ?? '',
        },
      })
  }, [profile])

  const set = (k: keyof ProfileIn) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }))
  const setLink = (k: keyof ProfileIn['links']) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, links: { ...f.links, [k]: e.target.value } }))

  async function addResumes() {
    if (!staged.length) return
    for (const file of staged) await upload.mutateAsync({ file })
    setStaged([])
  }

  return (
    <div className="mx-auto max-w-4xl space-y-12 px-6 py-16 lg:py-20">
      <header className="space-y-3">
        <button
          onClick={onBack}
          className="font-mono text-[11px] tracking-[0.22em] text-cream-soft uppercase hover:text-marigold"
        >
          ← back to the desk
        </button>
        <h1 className="font-serif text-5xl font-medium tracking-[-0.02em] text-cream sm:text-6xl">
          Your profile<span className="text-marigold">.</span>
        </h1>
        <p className="max-w-xl text-cream-soft">
          Set up once. Identity &amp; links live here; your résumé library saves you the re-upload on
          every run.
        </p>
      </header>

      {/* identity */}
      <section className="space-y-5">
        <p className="font-mono text-[11px] tracking-[0.22em] text-marigold uppercase">01 · identity</p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="name" value={form.name ?? ''} onChange={set('name')} placeholder="Ada Lovelace" />
          <Field label="email" value={form.email ?? ''} onChange={set('email')} placeholder="ada@example.com" />
          <Field label="phone" value={form.phone ?? ''} onChange={set('phone')} placeholder="+1 …" />
          <Field label="location" value={form.location ?? ''} onChange={set('location')} placeholder="Long Beach, CA" />
          <Field label="work authorization" value={form.work_auth ?? ''} onChange={set('work_auth')} placeholder="US citizen / H-1B / …" />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field label="github" value={form.links.github ?? ''} onChange={setLink('github')} placeholder="github.com/…" />
          <Field label="linkedin" value={form.links.linkedin ?? ''} onChange={setLink('linkedin')} placeholder="linkedin.com/in/…" />
          <Field label="portfolio" value={form.links.portfolio ?? ''} onChange={setLink('portfolio')} placeholder="yoursite.com" />
        </div>
        <div className="flex items-center gap-4">
          <Button
            onClick={() => save.mutate(form)}
            disabled={save.isPending}
            className="h-11 rounded-md bg-marigold px-6 font-mono text-xs tracking-[0.2em] text-ink uppercase transition hover:bg-marigold hover:brightness-95 disabled:opacity-40"
          >
            {save.isPending ? 'saving…' : 'Save profile'}
          </Button>
          {save.isSuccess && !save.isPending && (
            <span className="font-mono text-xs text-cream-soft">saved ✓</span>
          )}
        </div>
      </section>

      {/* résumé library */}
      <section className="space-y-5">
        <p className="font-mono text-[11px] tracking-[0.22em] text-marigold uppercase">
          02 · résumé library
        </p>

        {resumes.length > 0 ? (
          <ul className="sheet-sm divide-y divide-border overflow-hidden">
            {resumes.map((r) => (
              <li key={r.id} className="flex items-center justify-between gap-3 px-4 py-3">
                <span className="flex min-w-0 items-center gap-3">
                  <span aria-hidden className="text-accent">§</span>
                  <span className="truncate font-mono text-sm text-ink">{r.label || r.filename}</span>
                  {r.is_default && (
                    <span className="shrink-0 rounded bg-marigold/20 px-2 py-0.5 font-mono text-[10px] tracking-[0.15em] text-marigold uppercase">
                      default
                    </span>
                  )}
                </span>
                <span className="flex shrink-0 items-center gap-1">
                  {!r.is_default && (
                    <button
                      onClick={() => setDefault.mutate(r.id)}
                      className="rounded px-2 py-1 font-mono text-xs text-ink-soft hover:text-accent"
                    >
                      make default
                    </button>
                  )}
                  <button
                    onClick={() => del.mutate(r.id)}
                    aria-label={`Delete ${r.label || r.filename}`}
                    className="rounded px-2 py-1 font-mono text-xs text-ink-soft hover:text-gap"
                  >
                    remove
                  </button>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="font-mono text-sm text-cream-soft">No résumés yet — add a .tex below.</p>
        )}

        {/* stage one or more .tex, then add them all to the library */}
        <Dropzone
          files={staged}
          onChange={setStaged}
          title="Add résumés to your library"
          hint={
            <>
              Drop one or more <code className="font-mono text-accent">.tex</code> files — reuse them
              on any run, no re-upload.
            </>
          }
        />
        <div className="flex items-center gap-4">
          <Button
            onClick={addResumes}
            disabled={!staged.length || upload.isPending}
            className="h-11 rounded-md bg-cream-soft/10 px-5 font-mono text-xs tracking-[0.15em] text-cream uppercase transition hover:bg-cream-soft/20 disabled:opacity-40"
          >
            {upload.isPending
              ? 'adding…'
              : `Add ${staged.length ? `${staged.length} ` : ''}to library`}
          </Button>
          {upload.isError && (
            <p role="alert" className="font-mono text-xs text-gap-hi">
              {(upload.error as Error).message}
            </p>
          )}
        </div>
      </section>
    </div>
  )
}
