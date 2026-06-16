import React, { useEffect, useState, useCallback } from 'react';
import { API_BASE } from '../config';
import { DEMO_DECISIONS, isDemoFounder } from '../demo';
import '../styles/DecisionHistory.css';

interface Decision {
  id: string;
  type: string;
  decision_text: string;
  made_at: string;
  outcome?: string;
  impact?: string;
}

interface DecisionHistoryProps {
  founderId: string;
}

const LABEL: Record<string, string> = {
  decide: 'Decided',
  delegate: 'Delegated',
  dismiss: 'Dismissed'
};

const DecisionHistory: React.FC<DecisionHistoryProps> = ({ founderId }) => {
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchDecisions = useCallback(async () => {
    if (isDemoFounder(founderId)) {
      setDecisions(DEMO_DECISIONS as Decision[]);
      setLoading(false);
      return;
    }
    try {
      const response = await fetch(
        `${API_BASE}/founders/${founderId}/decisions?limit=20`
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setDecisions(await response.json());
    } catch (error) {
      console.error('Failed to fetch decision history:', error);
    } finally {
      setLoading(false);
    }
  }, [founderId]);

  useEffect(() => {
    fetchDecisions();
  }, [fetchDecisions]);

  return (
    <div className="bezel history">
      <div className="bezel__core">
        <span className="bezel__sheen" aria-hidden="true" />
        <div className="history__head">
          <span className="eyebrow">Decision trail</span>
          <h3>How you've been deciding</h3>
        </div>

        {loading ? (
          <p className="history__loading">Loading your trail…</p>
        ) : decisions.length === 0 ? (
          <p className="history__empty">No decisions logged yet.</p>
        ) : (
          <ol className="trail">
            {decisions.map((d) => (
              <li key={d.id} className={`trail__item is-${d.type}`}>
                <span className="trail__rail" aria-hidden="true" />
                <div className="trail__head">
                  <span className="trail__type">{LABEL[d.type] || d.type}</span>
                  <span className="trail__date">
                    {new Date(d.made_at).toLocaleDateString()}
                  </span>
                </div>
                <p className="trail__text">{d.decision_text}</p>
                {d.outcome && <p className="trail__outcome">{d.outcome}</p>}
                {d.impact && (
                  <span className={`trail__impact is-${d.impact}`}>{d.impact}</span>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
};

export default DecisionHistory;
