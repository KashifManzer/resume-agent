import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))

/** Load a saved ATS form fixture into the jsdom document body. */
export function loadFixture(name: string): void {
  document.body.innerHTML = readFileSync(join(here, 'fixtures', name), 'utf8')
}
