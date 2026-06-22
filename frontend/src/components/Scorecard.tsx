import React, { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '../config';
import { isDemoFounder } from '../demo';
import Sparkline from './charts/Sparkline';
import '../styles/scorecard.css';

interface Metric {
  id: string;
  name: string;
  owner?: string | null;
  target?: number | null;
  unit?: string | null;
  direction: string;
  latest?: number | null;
  on_track?: boolean | null;
  series: number[];
}

const DEMO_SCORECARD: Metric[] = [
  { id: 'm1', name: 'MRR', owner: 'You', target: 20000, unit: '$', direction: 'up', latest: 18000, on_track: false, series: [16000, 16500, 17000, 17200, 17600, 18000] },
  { id: 'm2', name: 'Net revenue retention', owner: 'CS lead', target: 110, unit: '%', direction: 'up', latest: 104, on_track: false, series: [112, 110, 108, 106, 105, 104] },
  { id: 'm3', name: 'Churn', owner: 'CS lead', target: 5, unit: '%', direction: 'down', latest: 3.2, on_track: true, series: [2.5, 2.8, 3, 3.5, 3.1, 3.2] },
  { id: 'm4', name: 'Pipeline created', owner: 'Sales', target: 50000, unit: '$', direction: 'up', latest: 62000, on_track: true, series: [40000, 44000, 48000, 51000, 58000, 62000] }
];

const fmt = (v: number | null | undefined, unit?: string | null) => {
  if (v === null || v === undefined) return '—';
  if (unit === '$') return v >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${v}`;
  if (unit === '%') return `${v}%`;
  return `${v}`;
};

const ReadingInput: React.FC<{ onAdd: (v: number) => void }> = ({ onAdd }) => {
  const [v, setV] = useState('');
  const submit = () => {
    const n = Number(v);
    if (v !== '' && !Number.isNaN(n)) {
      onAdd(n);
      setV('');
    }
  };
  return (
    <input
      className="sc__log"
      value={v}
      onChange={(e) => setV(e.target.value)}
      onKeyDown={(e) => e.key === 'Enter' && submit()}
      placeholder="log"
      inputMode="decimal"
      title="Log this week's actual"
    />
  );
};

const Scorecard: React.FC<{ founderId: string }> = ({ founderId }) => {
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [name, setName] = useState('');
  const [owner, setOwner] = useState('');
  const [target, setTarget] = useState('');
  const [unit, setUnit] = useState('$');
  const [direction, setDirection] = useState('up');
  const demo = isDemoFounder(founderId);

  const load = useCallback(async () => {
    if (demo) {
      setMetrics(DEMO_SCORECARD);
      return;
    }
    try {
      const r = await apiFetch(`/founders/${founderId}/scorecard`);
      if (!r.ok) throw new Error();
      setMetrics(await r.json());
    } catch {
      setMetrics([]);
    }
  }, [founderId, demo]);

  useEffect(() => {
    load();
  }, [load]);

  const addMetric = async () => {
    if (!name.trim()) return;
    const body = {
      name: name.trim(),
      owner: owner.trim() || null,
      target: target ? Number(target) : null,
      unit,
      direction
    };
    if (demo) {
      setMetrics((m) => [...m, { id: `m${Date.now()}`, ...body, latest: null, on_track: null, series: [] } as Metric]);
    } else {
      await apiFetch(`/founders/${founderId}/scorecard/metrics`, { method: 'POST', body: JSON.stringify(body) });
      await load();
    }
    setName('');
    setOwner('');
    setTarget('');
  };

  const addReading = async (id: string, value: number) => {
    if (demo) return;
    await apiFetch(`/founders/${founderId}/scorecard/metrics/${id}/readings`, {
      method: 'POST',
      body: JSON.stringify({ value })
    });
    load();
  };

  return (
    <div className="bezel scorecard">
      <div className="bezel__core">
        <span className="bezel__sheen" aria-hidden="true" />
        <div className="chat__head">
          <span className="eyebrow">Precision Scorecard — owner · target vs actual</span>
        </div>

        <ul className="sc__list">
          {metrics.length === 0 && <li className="chat__empty">No metrics yet. Add one below.</li>}
          {metrics.map((m) => (
            <li key={m.id} className="sc__row">
              <span
                className="sc__dot"
                data-state={m.on_track === null || m.on_track === undefined ? 'none' : m.on_track ? 'ok' : 'off'}
              />
              <div className="sc__id">
                <span className="sc__name">{m.name}</span>
                {m.owner && <span className="sc__owner">{m.owner}</span>}
              </div>
              {m.series && m.series.length > 1 && (
                <span className="sc__spark">
                  <Sparkline points={m.series} accent={m.on_track === false ? 'var(--rose)' : 'var(--emerald)'} />
                </span>
              )}
              <span className="sc__nums">
                <span className="sc__actual">{fmt(m.latest, m.unit)}</span>
                <span className="sc__target">/ {fmt(m.target, m.unit)} {m.direction === 'down' ? '↓' : '↑'}</span>
              </span>
              {!demo && <ReadingInput onAdd={(v) => addReading(m.id, v)} />}
            </li>
          ))}
        </ul>

        <div className="sc__make">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Metric (e.g. MRR)" />
          <input value={owner} onChange={(e) => setOwner(e.target.value)} placeholder="Owner" />
          <input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="Target" inputMode="decimal" />
          <select value={unit} onChange={(e) => setUnit(e.target.value)} title="Unit">
            <option value="$">$</option>
            <option value="%">%</option>
            <option value="">#</option>
          </select>
          <select value={direction} onChange={(e) => setDirection(e.target.value)} title="Better when">
            <option value="up">↑ higher</option>
            <option value="down">↓ lower</option>
          </select>
          <button className="btn btn--primary group" onClick={addMetric}>
            Add<span className="btn__icon" aria-hidden="true">↗</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default Scorecard;
