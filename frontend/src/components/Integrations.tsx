import React, { useEffect, useState, useCallback } from 'react';
import { API_BASE } from '../config';
import { isDemoFounder } from '../demo';
import '../styles/chat.css';

interface Integration {
  service: string;
  status: string;
  last_sync_at?: string | null;
}

const DEMO_SOURCES: Integration[] = [
  { service: 'stripe', status: 'success' },
  { service: 'slack', status: 'success' },
  { service: 'email', status: 'success' },
  { service: 'calendar', status: 'success' }
];

const Integrations: React.FC<{ founderId: string }> = ({ founderId }) => {
  const [list, setList] = useState<Integration[]>([]);
  const [key, setKey] = useState('');
  const [msg, setMsg] = useState('');
  const demo = isDemoFounder(founderId);

  const load = useCallback(async () => {
    if (demo) {
      setList(DEMO_SOURCES);
      return;
    }
    try {
      const r = await fetch(`${API_BASE}/founders/${founderId}/integrations`);
      if (!r.ok) throw new Error();
      setList(await r.json());
    } catch {
      setList([]);
    }
  }, [founderId, demo]);

  useEffect(() => {
    load();
  }, [load]);

  const connectGranola = async () => {
    if (!key.trim()) return;
    if (demo) {
      setMsg('Demo mode — connecting works in the live app.');
      return;
    }
    try {
      const r = await fetch(`${API_BASE}/founders/${founderId}/integrations/granola`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ access_token: key.trim() })
      });
      if (!r.ok) throw new Error();
      setKey('');
      setMsg('Granola connected ✓');
      load();
    } catch {
      setMsg('Failed to connect — check the key and that the backend is running.');
    }
  };

  return (
    <div className="bezel integrations">
      <div className="bezel__core">
        <span className="bezel__sheen" aria-hidden="true" />
        <div className="chat__head">
          <span className="eyebrow">Connected sources</span>
        </div>

        <ul className="src__list">
          {list.length === 0 && <li className="chat__empty">No sources connected yet.</li>}
          {list.map((i) => (
            <li key={i.service} className="src__item">
              <span className="src__dot" data-ok={i.status === 'success'} />
              <span className="src__name">{i.service}</span>
              <span className="src__status">{i.status || '—'}</span>
            </li>
          ))}
        </ul>

        <div className="src__connect">
          <span className="card__spark-k">Connect Granola — paste your API key</span>
          <div className="chat__input">
            <input
              value={key}
              onChange={(e) => setKey(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && connectGranola()}
              placeholder="grn_…"
            />
            <button className="btn btn--primary group" onClick={connectGranola}>
              Connect
              <span className="btn__icon" aria-hidden="true">↗</span>
            </button>
          </div>
          {msg && <p className="src__msg">{msg}</p>}
          <p className="src__hint">Granola API keys require their Business/Enterprise plan.</p>
        </div>
      </div>
    </div>
  );
};

export default Integrations;
