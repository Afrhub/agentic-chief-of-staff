import React, { useEffect, useState } from 'react';
import { apiFetch } from '../config';
import '../styles/onboarding.css';

interface Pack { id: string; name: string; }
interface Metric { name: string; target?: number | null; unit?: string | null; direction: string; }
interface Agent { axis: string; name: string; role: string; source: string; avatar?: string; }

const STEPS = ['Welcome', 'Industry', 'Targets', 'Sources', 'Your team'];

const fmtTarget = (m: Metric) => {
  if (m.target == null) return '—';
  const u = m.unit || '';
  if (u === '$') return m.target >= 1000 ? `$${m.target / 1000}k` : `$${m.target}`;
  return `${m.target}${u}`;
};

const Onboarding: React.FC<{ founderId: string; onDone: () => void }> = ({ founderId, onDone }) => {
  const [step, setStep] = useState(0);
  const [packs, setPacks] = useState<Pack[]>([]);
  const [pack, setPack] = useState('saas');
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [fleet, setFleet] = useState<Agent[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiFetch('/packs').then((r) => r.json()).then(setPacks).catch(() => {});
    apiFetch('/agents/fleet').then((r) => r.json()).then((d) => setFleet(d.agents || [])).catch(() => {});
  }, []);

  const next = async () => {
    if (step === 1) {
      // Commit the chosen industry: set the pack, reset the default targets to it, load them.
      setBusy(true);
      try {
        await apiFetch(`/founders/${founderId}`, { method: 'POST', body: JSON.stringify({ pack }) });
        await apiFetch(`/founders/${founderId}/scorecard/calibrate?reset=true`, { method: 'POST' });
        const sc = await apiFetch(`/founders/${founderId}/scorecard`).then((r) => r.json());
        setMetrics(Array.isArray(sc) ? sc : []);
      } catch {
        /* non-blocking — they can set targets later in the Scorecard */
      }
      setBusy(false);
    }
    if (step < STEPS.length - 1) setStep(step + 1);
    else onDone();
  };

  return (
    <div className="auth-screen">
      <div className="bezel onb reveal">
        <div className="bezel__core">
          <span className="bezel__sheen" aria-hidden="true" />
          <div className="onb__head">
            <div className="auth-brand">
              <span className="island__mark" aria-hidden="true" />
              <span className="island__name">dCern</span>
            </div>
            <div className="onb__steps">
              {STEPS.map((s, i) => (
                <span key={s} className={`onb__dot ${i <= step ? 'is-on' : ''}`} title={s} />
              ))}
            </div>
          </div>

          {step === 0 && (
            <div className="onb__body">
              <p className="eyebrow">Welcome</p>
              <h2 className="onb__title">Your AI Chief of Staff</h2>
              <p className="onb__lead">
                Five specialist agents each watch one axis of your business — money, customers, comms,
                meetings, ops. dCern only interrupts you when ≥2 of them independently agree something
                needs a decision. Let's set yours up in four quick steps.
              </p>
            </div>
          )}

          {step === 1 && (
            <div className="onb__body">
              <p className="eyebrow">Step 1 — Industry</p>
              <h2 className="onb__title">What kind of business?</h2>
              <p className="onb__lead">This sets your agents' vocabulary and seeds sensible default targets. Change it anytime.</p>
              <div className="onb__packs">
                {packs.map((p) => (
                  <button key={p.id} className={`onb__pack ${pack === p.id ? 'is-sel' : ''}`} onClick={() => setPack(p.id)}>
                    <span className="onb__pack-name">{p.name}</span>
                    <span className="onb__pack-id">{p.id}</span>
                  </button>
                ))}
                {!packs.length && <p className="onb__muted">Loading industries…</p>}
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="onb__body">
              <p className="eyebrow">Step 2 — Targets</p>
              <h2 className="onb__title">Your scorecard</h2>
              <p className="onb__lead">We've seeded these targets for your industry. Confirm now — fine-tune any of them anytime in the Scorecard.</p>
              <ul className="onb__metrics">
                {metrics.map((m) => (
                  <li key={m.name} className="onb__metric">
                    <span>{m.name}</span>
                    <span className="onb__metric-t">
                      {fmtTarget(m)} <em>{m.direction === 'down' ? '↓' : '↑'}</em>
                    </span>
                  </li>
                ))}
                {!metrics.length && <li className="onb__muted">Targets will appear here once your industry is set.</li>}
              </ul>
            </div>
          )}

          {step === 3 && (
            <div className="onb__body">
              <p className="eyebrow">Step 3 — Data sources</p>
              <h2 className="onb__title">Connect your tools</h2>
              <p className="onb__lead">
                Each agent reads from its own source. Connect them in your vault to go live; until then
                agents fall back to your scorecard. You can do this anytime — skip for now if you like.
              </p>
              <ul className="onb__sources">
                {fleet.map((a) => (
                  <li key={a.axis} className="onb__source">
                    <span className="onb__source-name">{a.source}</span>
                    <span className="onb__source-axis">{a.name} · {a.axis}</span>
                    <span className="onb__source-status">Not connected</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {step === 4 && (
            <div className="onb__body">
              <p className="eyebrow">Step 4 — Your team</p>
              <h2 className="onb__title">Meet your agents</h2>
              <p className="onb__lead">These five report to dCern, your Chief of Staff. You're all set.</p>
              <div className="onb__team">
                {fleet.map((a) => (
                  <div key={a.axis} className="onb__member">
                    <span className="onb__avatar">
                      {a.avatar && (
                        <img src={a.avatar} alt="" onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }} />
                      )}
                      <span>{a.name.charAt(0)}</span>
                    </span>
                    <span className="onb__member-name">{a.name}</span>
                    <span className="onb__member-role">{a.role}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="onb__nav">
            {step > 0 ? (
              <button className="onb__back" onClick={() => setStep(Math.max(0, step - 1))} disabled={busy}>
                Back
              </button>
            ) : (
              <span />
            )}
            <button className="btn btn--primary group" onClick={next} disabled={busy}>
              {busy ? 'Saving…' : step === STEPS.length - 1 ? 'Go to dashboard' : 'Continue'}
              <span className="btn__icon" aria-hidden="true">↗</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Onboarding;
