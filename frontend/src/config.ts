// API base URL.
//   - Self-hosted prod: leave REACT_APP_API_URL unset → '' → same-origin
//     relative calls (nginx proxies /founders, /slack, /health to the backend).
//   - Local dev against a backend on :8000: set REACT_APP_API_URL=http://localhost:8000
export const API_BASE = process.env.REACT_APP_API_URL || '';
