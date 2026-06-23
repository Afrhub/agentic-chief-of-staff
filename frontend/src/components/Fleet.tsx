import React, { useEffect, useState } from 'react';
import { apiFetch } from '../config';
import { DEMO_FLEET, isDemoFounder } from '../demo';
import '../styles/fleet.css';

interface Agent {
  axis: string;
  name: string;
  role: string;
  traits: string[];
  watches: string;
  model: string | null;
  source: string;
}

// Pretty model label — drop the vendor prefix noise for the UI.
const modelLabel = (m: string | null) => {
  if (!m) return 'model TBD';
  if (m.includes('haiku')) return 'Haiku 4.5';
  if (m.includes('sonnet')) return 'Sonnet 4.6';
  if (m.includes('opus')) return 'Opus 4.8';
  return m;
};

const Fleet: React.FC<{ founderId: string }> = ({ founderId }) => {
  const [agents, setAgents] = useState<Agent[]>([]);

  useEffect(() => {
    if (isDemoFounder(founderId)) {
      setAgents(DEMO_FLEET as Agent[]);
      return;
    }
    apiFetch('/agents/fleet')
      .then((r) => r.json())
      .then((d) => setAgents(d.agents || []))
      .catch(() => setAgents(DEMO_FLEET as Agent[])); // fall back to identities if API is unreachable
  }, [founderId]);

  return (
    <div className="bezel fleet">
      <div className="bezel__core">
        <span className="bezel__sheen" aria-hidden="true" />
        <div className="chat__head">
          <span className="eyebrow">Your team — five specialists, one Chief of Staff</span>
        </div>
        <p className="fleet__intro">
          Each agent watches a single business axis and reports a structured signal.
          <strong> dCern</strong> only interrupts you when ≥2 of them independently agree.
        </p>

        <div className="fleet__grid">
          {agents.map((a) => (
            <div className="fleet-card" key={a.axis}>
              <div className="fleet-card__top">
                <span className="fleet-card__avatar" data-axis={a.axis} aria-hidden="true">
                  {a.name.charAt(0)}
                </span>
                <div className="fleet-card__who">
                  <span className="fleet-card__name">{a.name}</span>
                  <span className="fleet-card__role">{a.role}</span>
                </div>
                <span className="fleet-card__axis">{a.axis}</span>
              </div>

              <p className="fleet-card__watches">
                <span className="fleet-card__label">Watches</span>
                {a.watches}
              </p>

              <div className="fleet-card__traits">
                {a.traits.map((t) => (
                  <span className="fleet-chip" key={t}>
                    {t}
                  </span>
                ))}
              </div>

              <div className="fleet-card__foot">
                <span className="fleet-card__src" data-live={a.source !== 'scorecard'}>
                  {a.source === 'scorecard' ? 'scorecard' : `${a.source} · live`}
                </span>
                <span className="fleet-card__model">{modelLabel(a.model)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Fleet;
