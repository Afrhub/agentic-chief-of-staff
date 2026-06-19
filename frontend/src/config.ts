// API base URL.
//   - Self-hosted prod: leave REACT_APP_API_URL unset → '' → same-origin
//     relative calls (nginx proxies /founders, /slack, /health to the backend).
//   - Local dev against a backend on :8000: set REACT_APP_API_URL=http://localhost:8000
export const API_BASE = process.env.REACT_APP_API_URL || '';

// Authenticated fetch: prepends API_BASE and attaches the login session token.
// Components call apiFetch('/founders/...') instead of fetch(`${API_BASE}...`).
export async function apiFetch(path: string, opts: RequestInit = {}): Promise<Response> {
  const token = localStorage.getItem('token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((opts.headers as Record<string, string>) || {}),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return fetch(`${API_BASE}${path}`, { ...opts, headers });
}
