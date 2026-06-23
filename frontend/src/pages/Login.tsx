import React, { useState } from 'react';
import { apiFetch } from '../config';
import '../styles/Dashboard.css';
import '../styles/fx.css';
import '../styles/chat.css';

// Email + password onboarding. On success stores {token, founder_id} and hands
// the founder id up to App, which swaps in the live dashboard.
const Login: React.FC<{ onAuthed: (founderId: string, isNew?: boolean) => void }> = ({ onAuthed }) => {
  const [mode, setMode] = useState<'signup' | 'login'>('signup');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const submit = async () => {
    if (busy) return;
    setErr('');
    if (!email.includes('@') || password.length < 8) {
      setErr('Enter a valid email and a password of at least 8 characters.');
      return;
    }
    setBusy(true);
    try {
      const r = await apiFetch(`/auth/${mode}`, {
        method: 'POST',
        body: JSON.stringify({ email: email.trim(), password }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || 'Something went wrong.');
      localStorage.setItem('token', data.token);
      localStorage.setItem('founder_id', data.founder_id);
      if (mode === 'signup') localStorage.setItem('dcern_onboarding', 'pending');
      onAuthed(data.founder_id, mode === 'signup');
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Something went wrong.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-screen">
      <div className="bezel auth-card reveal">
        <div className="bezel__core">
          <span className="bezel__sheen" aria-hidden="true" />
          <div className="auth-brand">
            <span className="island__mark" aria-hidden="true" />
            <span className="island__name">dCern</span>
          </div>
          <p className="eyebrow">{mode === 'signup' ? 'Create your account' : 'Welcome back'}</p>

          <div className="auth-fields">
            <input
              className="auth-input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              autoComplete="email"
            />
            <input
              className="auth-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && submit()}
              placeholder="Password (min 8 characters)"
              autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
            />
            {err && <p className="auth-err">{err}</p>}
            <button className="btn btn--primary group" onClick={submit} disabled={busy}>
              {busy ? 'Working…' : mode === 'signup' ? 'Create account' : 'Log in'}
              <span className="btn__icon" aria-hidden="true">↗</span>
            </button>
          </div>

          <button
            className="auth-toggle"
            onClick={() => {
              setErr('');
              setMode(mode === 'signup' ? 'login' : 'signup');
            }}
          >
            {mode === 'signup'
              ? 'Already have an account? Log in'
              : 'New here? Create an account'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Login;
