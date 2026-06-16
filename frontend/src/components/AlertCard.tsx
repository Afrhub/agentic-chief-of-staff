import React, { useState } from 'react';
import Sparkline from './charts/Sparkline';
import '../styles/AlertCard.css';

interface Alert {
  id: string;
  type: string;
  title: string;
  what_happened: string;
  why_it_matters: string;
  what_to_do_next: string;
  next_decision: string;
  precedent_context?: string | null;
  trend?: number[];
  data_freshness: Record<string, string>;
  confidence: number;
  triggered_at: string;
}

interface AlertCardProps {
  alert: Alert;
  index?: number;
  onDecide: (text: string) => void;
  onDelegate: (to: string) => void;
  onDismiss: (reason: string) => void;
}

const TYPE_META: Record<string, { label: string; accent: string }> = {
  revenue_anomaly: { label: 'Revenue anomaly', accent: 'amber' },
  churn_signal: { label: 'Churn signal', accent: 'rose' },
  investor_contact: { label: 'Investor contact', accent: 'emerald' },
  team_conflict: { label: 'Team escalation', accent: 'orange' },
  competitor_move: { label: 'Competitor move', accent: 'violet' }
};

const freshnessState = (status: string): 'ok' | 'warn' | 'bad' => {
  if (status.includes('❌')) return 'bad';
  if (status.includes('⚠')) return 'warn';
  return 'ok';
};

const cleanFreshness = (status: string) =>
  status.replace(/[✓⚠️❌]/g, '').replace(/\(.*?\)/g, '').trim();

const AlertCard: React.FC<AlertCardProps> = ({
  alert,
  onDecide,
  onDelegate,
  onDismiss
}) => {
  const [action, setAction] = useState<'none' | 'decide' | 'delegate' | 'dismiss'>('none');
  const [input, setInput] = useState('');

  const meta = TYPE_META[alert.type] || { label: 'Signal', accent: 'violet' };
  const pct = Math.round((alert.confidence || 0) * 100);

  const handleSubmit = () => {
    if (action === 'decide') onDecide(input || 'Handling it');
    else if (action === 'delegate') onDelegate(input || 'Team member');
    else if (action === 'dismiss') onDismiss(input || 'Not urgent');
    setAction('none');
    setInput('');
  };

  const placeholder =
    action === 'decide'
      ? 'What did you decide?'
      : action === 'delegate'
      ? 'Who should own this?'
      : 'Why dismiss? (optional)';

  return (
    <article className={`bezel accent-${meta.accent}`}>
      <div className="bezel__core">
        <span className="bezel__sheen" aria-hidden="true" />

        {/* Header: type eyebrow + confidence meter */}
        <div className="card__top">
          <span className="type-tag">
            <span className="type-tag__dot" />
            {meta.label}
          </span>

          <div className="conf" title={`${pct}% confidence`}>
            <svg className="conf__ring" viewBox="0 0 44 44" aria-hidden="true">
              <circle className="conf__track" cx="22" cy="22" r="19" />
              <circle
                className="conf__value"
                cx="22"
                cy="22"
                r="19"
                strokeDasharray={`${(pct / 100) * 119.4} 119.4`}
              />
            </svg>
            <span className="conf__pct">{pct}</span>
          </div>
        </div>

        <h2 className="card__title">{alert.title.replace(/^Decision:\s*/, '')}</h2>

        {/* Freshness pills */}
        <div className="fresh">
          {Object.entries(alert.data_freshness).map(([src, status]) => (
            <span key={src} className={`fresh__pill is-${freshnessState(status)}`}>
              <span className="fresh__dot" />
              {src} · {cleanFreshness(status)}
            </span>
          ))}
        </div>

        {/* Inline trend sparkline */}
        {alert.trend && alert.trend.length > 1 && (
          <div className="card__spark">
            <span className="card__spark-k">14-day trend</span>
            <Sparkline points={alert.trend} accent="var(--accent)" />
          </div>
        )}

        {/* Body sections */}
        <div className="sections">
          <section className="sec">
            <span className="sec__k">What happened</span>
            <p className="sec__v">{alert.what_happened}</p>
          </section>

          <section className="sec">
            <span className="sec__k">Why it matters</span>
            <p className="sec__v">{alert.why_it_matters}</p>
          </section>

          {alert.precedent_context && (
            <section className="sec sec--precedent">
              <span className="sec__k">What happened last time</span>
              <p className="sec__v">{alert.precedent_context}</p>
            </section>
          )}

          <section className="sec">
            <span className="sec__k">What to do next</span>
            <p className="sec__v">{alert.what_to_do_next}</p>
          </section>
        </div>

        {/* Decision prompt */}
        <div className="decision">
          <span className="decision__k">The decision</span>
          <p className="decision__q">{alert.next_decision}</p>
        </div>

        {/* Actions */}
        <div className="actions">
          {action === 'none' ? (
            <>
              <button className="btn btn--primary group" onClick={() => setAction('decide')}>
                Decide
                <span className="btn__icon" aria-hidden="true">↗</span>
              </button>
              <button className="btn btn--ghost" onClick={() => setAction('delegate')}>
                Delegate
              </button>
              <button className="btn btn--ghost" onClick={() => setAction('dismiss')}>
                Dismiss
              </button>
            </>
          ) : (
            <div className="actions__input">
              <input
                autoFocus
                type="text"
                placeholder={placeholder}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
              />
              <button className="btn btn--primary group" onClick={handleSubmit}>
                Confirm
                <span className="btn__icon" aria-hidden="true">↗</span>
              </button>
              <button
                className="btn btn--quiet"
                onClick={() => {
                  setAction('none');
                  setInput('');
                }}
              >
                Cancel
              </button>
            </div>
          )}
        </div>

        <div className="card__foot">
          Triggered {new Date(alert.triggered_at).toLocaleString()}
        </div>
      </div>
    </article>
  );
};

export default AlertCard;
