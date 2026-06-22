import React, { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '../config';
import { isDemoFounder } from '../demo';
import '../styles/board.css';

interface Card {
  id: string;
  type: string;
  title: string;
  next_decision?: string | null;
  confidence?: number;
  note?: string | null;
  impact?: string | null;
}
type BoardData = Record<string, Card[]>;

const COLUMNS: { key: string; label: string }[] = [
  { key: 'new', label: 'New' },
  { key: 'decided', label: 'Decision made' },
  { key: 'delegated', label: 'Delegated' },
  { key: 'deferred', label: 'Deferred' },
  { key: 'dismissed', label: 'Dismissed' },
  { key: 'done', label: 'Done' }
];

const DEMO_BOARD: BoardData = {
  new: [
    { id: 'a1', type: 'revenue_anomaly', title: 'Should we pause ads and focus on retention?', confidence: 0.88 },
    { id: 'a2', type: 'investor_contact', title: 'How fast do we respond to the Sequoia partner?', confidence: 0.91 }
  ],
  decided: [
    { id: 'd1', type: 'churn_signal', title: 'Roll back the price change for legacy accounts', note: 'Decided: roll back for accounts >12mo' }
  ],
  delegated: [
    { id: 'g1', type: 'team_conflict', title: 'Resolve the eng/design deadline clash', note: 'Delegated to VP Eng' }
  ],
  deferred: [
    { id: 'f1', type: 'competitor_move', title: "Respond to competitor's new pricing", note: 'Deferred — waiting on CFO (on leave) until Mon' }
  ],
  dismissed: [
    { id: 'x1', type: 'revenue_anomaly', title: 'One-off refund spike', note: 'Dismissed: seasonal, not a trend' }
  ],
  done: [
    { id: 'z1', type: 'revenue_anomaly', title: 'Paused ads during the Q1 dip', impact: 'positive' }
  ]
};

const impactLabel = (i?: string | null) =>
  i === 'positive' ? '👍 right call' : i === 'negative' ? '👎 missed' : i === 'neutral' ? '• neutral' : '';

const Board: React.FC<{ founderId: string }> = ({ founderId }) => {
  const [board, setBoard] = useState<BoardData>({});
  const demo = isDemoFounder(founderId);

  const load = useCallback(async () => {
    if (demo) {
      setBoard(DEMO_BOARD);
      return;
    }
    try {
      const r = await apiFetch(`/founders/${founderId}/board`);
      if (!r.ok) throw new Error();
      setBoard(await r.json());
    } catch {
      setBoard({});
    }
  }, [founderId, demo]);

  useEffect(() => {
    load();
  }, [load]);

  // ponytail: native prompt/confirm to capture the value in a compact board card;
  // the rich feed keeps the inline-input flow.
  const post = async (path: string, body: object) => {
    await apiFetch(`/founders/${founderId}/alerts/${path}`, { method: 'POST', body: JSON.stringify(body) });
    load();
  };
  const onDecide = (id: string) => { if (demo) return; const t = window.prompt('What did you decide?'); if (t !== null) post(`${id}/decide`, { decision_text: t || 'Handled' }); };
  const onDelegate = (id: string) => { if (demo) return; const to = window.prompt('Delegate to whom?'); if (to) post(`${id}/delegate`, { delegated_to: to }); };
  const onDefer = (id: string) => { if (demo) return; const w = window.prompt('Waiting on who/what?'); if (w !== null) post(`${id}/defer`, { waiting_on: w || 'more info' }); };
  const onDismiss = (id: string) => { if (demo) return; if (window.confirm('Dismiss this alert?')) post(`${id}/dismiss`, { reason: 'Dismissed from board' }); };
  const onVerify = (id: string, impact: string) => { if (demo) return; post(`${id}/verify`, { impact }); };

  return (
    <div className="board">
      {COLUMNS.map((col) => {
        const cards = board[col.key] || [];
        return (
          <div className={`board__col board__col--${col.key}`} key={col.key}>
            <div className="board__col-head">
              <span className="board__col-name">{col.label}</span>
              <span className="board__col-count">{cards.length}</span>
            </div>
            <div className="board__cards">
              {cards.length === 0 && <p className="board__empty">—</p>}
              {cards.map((card) => (
                <div className="board__card" key={card.id}>
                  <span className="board__type">{card.type.replace(/_/g, ' ')}</span>
                  <p className="board__title">{card.title}</p>
                  {card.note && (col.key === 'deferred' || col.key === 'dismissed' || col.key === 'delegated' || col.key === 'decided') && (
                    <p className="board__note">{card.note}</p>
                  )}
                  {col.key === 'done' && card.impact && (
                    <span className={`board__impact is-${card.impact}`}>{impactLabel(card.impact)}</span>
                  )}
                  {col.key === 'new' && (
                    <div className="board__actions">
                      <button onClick={() => onDecide(card.id)}>Decide</button>
                      <button onClick={() => onDelegate(card.id)}>Delegate</button>
                      <button onClick={() => onDefer(card.id)}>Defer</button>
                      <button onClick={() => onDismiss(card.id)}>Dismiss</button>
                    </div>
                  )}
                  {(col.key === 'decided' || col.key === 'delegated') && (
                    <div className="board__actions">
                      <button onClick={() => onVerify(card.id, 'positive')}>✓ Worked</button>
                      <button onClick={() => onVerify(card.id, 'negative')}>✗ Didn't</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default Board;
