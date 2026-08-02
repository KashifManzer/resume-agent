import { describe, expect, test } from 'vitest'

import { detectFields } from '../src/content/detector'
import { loadFixture } from './util'

describe('detectFields', () => {
  test('greenhouse: detects fillable fields and skips the submit button', () => {
    loadFixture('greenhouse.html')
    const fields = detectFields(document)
    const names = fields.map((f) => f.descriptor.name)
    expect(names).toContain('first_name')
    expect(names).toContain('last_name')
    expect(names).toContain('email')
    expect(names).toContain('resume')
    // buttons are never fields
    expect(fields.some((f) => f.el.tagName === 'BUTTON')).toBe(false)
    // the file input keeps its type
    expect(fields.find((f) => f.descriptor.name === 'resume')!.descriptor.type).toBe('file')
  })

  test('greenhouse: resolves <label for=id> text and required flag', () => {
    loadFixture('greenhouse.html')
    const email = detectFields(document).find((f) => f.descriptor.name === 'email')!
    expect(email.descriptor.label.toLowerCase()).toContain('email')
    expect(email.descriptor.required).toBe(true)
  })

  test('lever: resolves sibling label text without a for= attribute', () => {
    loadFixture('lever.html')
    const fields = detectFields(document)
    const name = fields.find((f) => f.descriptor.name === 'name')!
    expect(name.descriptor.label.toLowerCase()).toContain('full name')
    const linkedin = fields.find((f) => f.descriptor.name === 'urls[LinkedIn]')!
    expect(linkedin.descriptor.label.toLowerCase()).toContain('linkedin')
  })

  test('ashby: resolves label[for] and excludes the reCAPTCHA field', () => {
    loadFixture('ashby.html')
    const fields = detectFields(document)
    const name = fields.find((f) => f.descriptor.id === '_systemfield_name')!
    expect(name.descriptor.label).toBe('Name')
    expect(fields.some((f) => /captcha/.test(f.descriptor.name))).toBe(false)
  })

  test('assigns sequential field_ref matching array position', () => {
    loadFixture('lever.html')
    const fields = detectFields(document)
    expect(fields.map((f) => f.descriptor.field_ref)).toEqual(fields.map((_, i) => i))
  })

  test('detects an opacity:0 résumé file input (styled upload button hides it)', () => {
    // Lever/Greenhouse pattern: the real <input type=file> sits at opacity:0
    // under a styled "Attach résumé" button. It must still be detected+fillable.
    document.body.innerHTML = `
      <input name="resume" id="resume-upload-input" type="file" style="opacity:0" />
      <input name="nickname" type="text" style="opacity:0" />
    `
    const names = detectFields(document).map((f) => f.descriptor.name)
    expect(names).toContain('resume') // file: opacity:0 is the normal hide, keep it
    expect(names).not.toContain('nickname') // text: opacity:0 is a honeypot tell, drop it
  })

  test('skips honeypot + hidden decoy fields, keeps the real one (T13)', () => {
    document.body.innerHTML = `
      <input name="email" type="email" />
      <input name="honeypot_email" type="text" />
      <input name="url" class="bot-field" type="text" />
      <input name="nickname" style="opacity:0" type="text" />
      <div aria-hidden="true"><input name="company" type="text" /></div>
    `
    const names = detectFields(document).map((f) => f.descriptor.name)
    expect(names).toEqual(['email']) // every decoy dropped, only the real field survives
  })
})
