import { readdirSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, test } from 'vitest'

// Hard rule (T12 trust boundary): the extension NEVER submits the form. This
// test fails if any content-script source grows a code path that could click a
// submit control or programmatically submit a form.
const contentDir = join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'content')

// .click( is caught by the /\.click\s*\(/ pattern too, listed for clarity.
const FORBIDDEN = [/\.submit\s*\(/, /requestSubmit/, /\.click\s*\(/]

describe('no auto-submit', () => {
  const files = readdirSync(contentDir).filter((f) => f.endsWith('.ts'))

  test('there is at least one content-script file to scan', () => {
    expect(files.length).toBeGreaterThan(0)
  })

  for (const file of files) {
    test(`${file} contains no submit/click code path`, () => {
      const src = readFileSync(join(contentDir, file), 'utf8')
      for (const pattern of FORBIDDEN) {
        expect(pattern.test(src), `${file} must not match ${pattern}`).toBe(false)
      }
    })
  }
})
