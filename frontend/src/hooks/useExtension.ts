import { useEffect, useState } from 'react'

/** True once the browser extension announces itself (T14). The content script
 *  sets `data-resume-agent` on <html> at document_start and fires an event; we
 *  read the flag on mount and listen for the event to cover either load order. */
export function useExtensionInstalled(): boolean {
  const [present, setPresent] = useState(
    () => typeof document !== 'undefined' && document.documentElement.dataset.resumeAgent != null,
  )
  useEffect(() => {
    // Normal case is already caught by the initializer (the content script sets
    // the flag at document_start, before the app mounts). Only late injection —
    // installing while this page is open — needs the event.
    if (present) return
    const onPresent = () => setPresent(true)
    window.addEventListener('resume-agent:present', onPresent)
    return () => window.removeEventListener('resume-agent:present', onPresent)
  }, [present])
  return present
}
