import React, { useMemo } from 'react';
import TrendChart, { TrendPoint } from './charts/TrendChart';
import Donut, { DonutSegment } from './charts/Donut';
import '../styles/charts.css';

interface PulseAlert {
  type: string;
  trend?: number[];
}

interface PulsePanelProps {
  alerts: PulseAlert[];
}

const TYPE_LABEL: Record<string, string> = {
  revenue_anomaly: 'Revenue',
  churn_signal: 'Churn',
  investor_contact: 'Investor',
  team_conflict: 'Team',
  competitor_move: 'Competitor'
};
const TYPE_COLOR: Record<string, string> = {
  revenue_anomaly: 'var(--amber)',
  churn_signal: 'var(--rose)',
  investor_contact: 'var(--emerald)',
  team_conflict: 'var(--orange)',
  competitor_move: 'var(--violet)'
};

// Deterministic 14-day MRR baseline ($K) so polling never re-randomises the chart.
const FALLBACK_MRR = [18.2, 18.4, 18.1, 18.5, 18.3, 18.6, 18.2, 18.0, 17.9, 18.1, 17.7, 17.3, 16.5, 16.0];

const PulsePanel: React.FC<PulsePanelProps> = ({ alerts }) => {
  const mrr: TrendPoint[] = useMemo(() => {
    const rev = alerts.find((a) => a.type === 'revenue_anomaly' && a.trend && a.trend.length);
    const series = rev?.trend && rev.trend.length ? rev.trend : FALLBACK_MRR;
    const n = series.length;
    return series.map((v, i) => ({
      label: i === n - 1 ? 'Today' : `${n - 1 - i}d ago`,
      value: v
    }));
  }, [alerts]);

  const mix: DonutSegment[] = useMemo(() => {
    const counts = new Map<string, number>();
    alerts.forEach((a) => counts.set(a.type, (counts.get(a.type) || 0) + 1));
    return Array.from(counts.entries()).map(([type, value]) => ({
      label: TYPE_LABEL[type] || type,
      value,
      color: TYPE_COLOR[type] || 'var(--violet)'
    }));
  }, [alerts]);

  return (
    <div className="bezel pulse">
      <div className="bezel__core">
        <span className="bezel__sheen" aria-hidden="true" />
        <div className="pulse__grid">
          <section className="pulse__main">
            <div className="pulse__head">
              <span className="eyebrow">Monthly recurring revenue · 14 days</span>
              <span className="pulse__delta">▼ 12% wk</span>
            </div>
            <TrendChart points={mrr} accent="var(--amber)" prefix="$" suffix="K" />
          </section>

          <section className="pulse__side">
            <span className="eyebrow">Where signals came from</span>
            <Donut segments={mix} />
            <ul className="legend">
              {mix.map((s) => (
                <li key={s.label} className="legend__item">
                  <span className="legend__dot" style={{ background: s.color }} />
                  {s.label}
                  <span className="legend__val">{s.value}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
};

export default PulsePanel;
