import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(<App />)

// PWA: register the service worker so the cockpit installs to the phone home screen + loads instantly.
// The worker caches ONLY the static shell — never live governance data (see public/sw.js).
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/app/sw.js', { scope: '/app/' }).catch(() => {})
  })
}
