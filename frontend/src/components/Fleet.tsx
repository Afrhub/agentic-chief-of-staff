import React, { useEffect, useState } from 'react';
import { apiFetch } from '../config';
import { DEMO_FLEET, isDemoFounder } from '../demo';
import '../styles/fleet.css';

interface Finding {
  has_signal: boolean;
  type?: string;
  confidence?: number;
  summary?: string;
}
interface Agent {
  axis: string;
  name: string;
  role: string;
  traits: string[];
  watches: string;
  model: string | null;
  source: string;
  connectors?: string[];
  tools?: string[];
  cadence?: string;
  avatar?: string;
  lastFinding?: Finding;
}
interface TeamOutcome {
  raised: boolean;
  axes: number;
  conf?: number;
  threshold?: number;
  flagged: string[];
  note?: string;
}
interface RunState {
  status: 'idle' | 'running' | 'done';
  finding?: Finding;
  team?: TeamOutcome;
}

const modelLabel = (m?: string | null) => {
  if (!m) return 'model TBD';
  if (m.includes('haiku')) return 'Haiku 4.5';
  if (m.includes('sonnet')) return 'Sonnet 4.6';
  if (m.includes('opus')) return 'Opus 4.8';
  return m;
};

// Mirror of the backend corroboration gate (coordinator.analyze_signals): >=2
// distinct types, judged on the strongest signal per type (top-2), with the bar
// lowered as more axes corroborate (floor 0.65). Used to assess a demo run.
function corroborate(agents: Agent[], findings: Record<string, Finding | undefined>): TeamOutcome {
  const flagged: string[] = [];
  const bestByType: Record<string, number> = {};
  agents.forEach((a) => {
    const f = findings[a.axis] ?? a.lastFinding;
    if (f?.has_signal) {
      flagged.push(a.name);
      const t = f.type || a.axis;
      bestByType[t] = Math.max(bestByType[t] || 0, f.confidence || 0.8);
    }
  });
  const types = Object.keys(bestByType);
  if (types.length < 2) return { raised: false, axes: types.length, flagged };
  const top = Object.values(bestByType).sort((x, y) => y - x).slice(0, 2);
  const conf = Math.min(0.95, top.reduce((s, v) => s + v, 0) / top.length);
  const threshold = Math.max(0.65, 0.8 - 0.05 * (types.length - 2));
  return { raised: conf >= threshold, axes: types.length, conf, threshold, flagged };
}

const Fleet: React.FC<{ founderId: string }> = ({ founderId }) => {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [runs, setRuns] = useState<Record<string, RunState>>({});
  const demo = isDemoFounder(founderId);

  useEffect(() => {
    if (demo) {
      setAgents(DEMO_FLEET as Agent[]);
      return;
    }
    apiFetch('/agents/fleet')
      .then((r) => r.json())
      .then((d) => setAgents(d.agents || []))
      .catch(() => setAgents(DEMO_FLEET as Agent[]));
  }, [demo]);

  const statusOf = (a: Agent): 'running' | 'flagging' | 'clear' => {
    const r = runs[a.axis];
    if (r?.status === 'running') return 'running';
    const f = r?.finding ?? a.lastFinding;
    return f?.has_signal ? 'flagging' : 'clear';
  };

  // A manual run triggers the whole fleet: this agent runs, the others assess on
  // the result, and the gate decides whether to raise an issue.
  const runAgent = async (a: Agent) => {
    setRuns((p) => ({ ...p, [a.axis]: { status: 'running' } }));

    if (demo) {
      setTimeout(() => {
        const findings: Record<string, Finding | undefined> = {};
        agents.forEach((x) => (findings[x.axis] = x.lastFinding));
        setRuns((p) => ({ ...p, [a.axis]: { status: 'done', finding: a.lastFinding, team: corroborate(agents, findings) } }));
      }, 900);
      return;
    }

    try {
      const res = await apiFetch(`/founders/${founderId}/agents/run`, { method: 'POST' }).then((r) => r.json());
      if (res.status === 'not_configured' || res.status === 'no_findings') {
        setRuns((p) => ({ ...p, [a.axis]: { status: 'done', team: { raised: false, axes: 0, flagged: [], note: res.detail || res.status } } }));
        return;
      }
      const findings: Record<string, any> = {};
      (res.findings || []).forEach((f: any) => (findings[f.axis] = f));
      const team: TeamOutcome = {
        raised: res.alert_status === 'surfaced',
        axes: res.signals || 0,
        flagged: (res.findings || []).filter((f: any) => f.has_signal).map((f: any) => f.axis),
      };
      setRuns((p) => ({ ...p, [a.axis]: { status: 'done', finding: findings[a.axis], team } }));
    } catch {
      setRuns((p) => ({ ...p, [a.axis]: { status: 'idle' } }));
    }
  };

  return (
    <div className="bezel fleet">
      <div className="bezel__core">
        <span className="bezel__sheen" aria-hidden="true" />
        <div className="chat__head">
          <span className="eyebrow">Your team — five specialists, one Chief of Staff</span>
        </div>
        <p className="fleet__intro">
          Each agent watches one axis and reports a structured signal. <strong>dCern</strong> only
          interrupts you when ≥2 of them independently agree. Expand a card to see what it reads and
          run it on demand — the rest of the team then assesses the result.
        </p>

        <div className="fleet__grid">
          {agents.map((a) => {
            const isOpen = open === a.axis;
            const st = statusOf(a);
            const run = runs[a.axis];
            const finding = run?.finding ?? a.lastFinding;
            return (
              <div className={`fleet-card ${isOpen ? 'is-open' : ''}`} key={a.axis}>
                <button className="fleet-card__top" onClick={() => setOpen(isOpen ? null : a.axis)} aria-expanded={isOpen}>
                  <span className="fleet-card__avatar" data-axis={a.axis} aria-hidden="true">
                    {a.avatar && (
                      <img
                        className="fleet-card__photo"
                        src={a.avatar}
                        alt=""
                        onError={(e) => {
                          (e.currentTarget as HTMLImageElement).style.display = 'none';
                        }}
                      />
                    )}
                    <span className="fleet-card__initial">{a.name.charAt(0)}</span>
                  </span>
                  <span className="fleet-card__who">
                    <span className="fleet-card__name">{a.name}</span>
                    <span className="fleet-card__role">{a.role}</span>
                  </span>
                  <span className={`fleet-status fleet-status--${st}`}>{st}</span>
                  <span className="fleet-card__chev" aria-hidden="true">{isOpen ? '▾' : '▸'}</span>
                </button>

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

                {isOpen && (
                  <div className="fleet-detail">
                    <div className="fleet-detail__row">
                      <span className="fleet-card__label">Connected to</span>
                      <div className="fleet-card__traits">
                        {(a.tools || [`${a.source} (MCP)`]).map((t) => (
                          <span className="fleet-chip" key={t}>
                            {t}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="fleet-detail__row">
                      <span className="fleet-card__label">Runs</span>
                      <span className="fleet-detail__val">
                        {a.cadence || 'On demand'}{' '}
                        <span className="fleet-detail__muted">(on-demand until the 24/7 deployment is on)</span>
                      </span>
                    </div>

                    <div className="fleet-detail__row">
                      <span className="fleet-card__label">Latest analysis</span>
                      {finding ? (
                        <span className="fleet-detail__val">
                          {finding.has_signal ? (
                            <>
                              <strong>
                                Flagged{finding.confidence ? ` · ${Math.round(finding.confidence * 100)}% conf` : ''}:
                              </strong>{' '}
                              {finding.summary}
                            </>
                          ) : (
                            <>No signal — {finding.summary}</>
                          )}
                        </span>
                      ) : (
                        <span className="fleet-detail__muted">Run the agent to see its latest read.</span>
                      )}
                    </div>

                    <button className="fleet-run" onClick={() => runAgent(a)} disabled={run?.status === 'running'}>
                      {run?.status === 'running' ? 'Running…' : run?.status === 'done' ? 'Run again' : 'Run now'}
                    </button>

                    {run?.status === 'done' && run.team && (
                      <div className={`fleet-team ${run.team.raised ? 'is-raised' : 'is-clear'}`}>
                        {run.team.note ? (
                          <span>{run.team.note}</span>
                        ) : (
                          <span>
                            <strong>{run.team.raised ? '⚠ Issue raised' : 'No issue raised'}</strong> — team assessed:{' '}
                            {run.team.flagged.length ? `${run.team.flagged.join(', ')} flagged` : 'no axis flagged'}
                            {run.team.axes >= 2 ? (
                              <>
                                {' '}· {run.team.axes} distinct axes
                                {run.team.conf != null
                                  ? ` (top-2 ${(run.team.conf * 100).toFixed(0)}% vs ${(run.team.threshold! * 100).toFixed(0)}% bar)`
                                  : ''}
                                {run.team.raised ? ' → added to the board' : ''}
                              </>
                            ) : (
                              <> · needs ≥2 corroborating axes</>
                            )}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default Fleet;
