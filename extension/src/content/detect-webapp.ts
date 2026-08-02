// Runs on the Resume Agent web app itself (T14). Its only job: tell the page the
// extension is installed, so the onboarding checklist can tick "extension" and
// hide the install CTA. Sets a DOM flag AND fires an event to cover either load
// order (this script vs. the app's own bundle). Touches nothing else on the page.
const version = chrome.runtime.getManifest().version
document.documentElement.dataset.resumeAgent = version
window.dispatchEvent(new CustomEvent('resume-agent:present', { detail: { version } }))
