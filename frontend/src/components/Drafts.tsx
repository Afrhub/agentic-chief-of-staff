import React, { useEffect, useState, useCallback } from 'react';
import { apiFetch } from '../config';
import { isDemoFounder } from '../demo';
import '../styles/chat.css';

interface Draft {
  id: string;
  channel: string;
  recipient?: string | null;
  subject?: string | null;
  body: string;
  status: string;
  instruction?: string | null;
}

const DEMO_DRAFT: Draft = {
  id: 'demo-draft',
  channel: 'email',
  recipient: 'partner@sequoia.com',
  subject: 'Re: updated metrics deck',
  body:
    "Hi —\n\nThanks for the note. I'll have the updated deck (MRR, retention, runway) to you before Friday, and I'm holding Thursday for a live walkthrough.\n\nQuick heads-up: we saw a short-term MRR dip this week from a pricing test; I'll include the diagnosis and the recovery plan so you have the full picture.\n\nBest,\n[Founder]",
  status: 'pending',
  instruction: 'Reply to the Sequoia partner about the deck'
};

const Drafts: React.FC<{ founderId: string }> = ({ founderId }) => {
  const [list, setList] = useState<Draft[]>([]);
  const [instruction, setInstruction] = useState('');
  const [channel, setChannel] = useState('email');
  const [busy, setBusy] = useState(false);
  const demo = isDemoFounder(founderId);

  const load = useCallback(async () => {
    if (demo) {
      setList([DEMO_DRAFT]);
      return;
    }
    try {
      const r = await apiFetch(`/founders/${founderId}/drafts?status=pending`);
      if (!r.ok) throw new Error();
      setList(await r.json());
    } catch {
      setList([]);
    }
  }, [founderId, demo]);

  useEffect(() => {
    load();
  }, [load]);

  const generate = async () => {
    const text = instruction.trim();
    if (!text || busy) return;
    if (demo) {
      setList((l) => [{ ...DEMO_DRAFT, id: `d${Date.now()}`, instruction: text }, ...l]);
      setInstruction('');
      return;
    }
    setBusy(true);
    try {
      const r = await apiFetch(`/founders/${founderId}/drafts`, {
        method: 'POST',
        body: JSON.stringify({ instruction: text, channel })
      });
      if (!r.ok) throw new Error();
      const d = await r.json();
      setList((l) => [d, ...l]);
      setInstruction('');
    } catch {
      /* surfaced via empty list */
    } finally {
      setBusy(false);
    }
  };

  const act = async (id: string, action: 'approve' | 'discard') => {
    setList((l) => l.filter((d) => d.id !== id)); // optimistic
    if (demo) return;
    try {
      await apiFetch(`/founders/${founderId}/drafts/${id}/${action}`, { method: 'POST' });
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="bezel drafts">
      <div className="bezel__core">
        <span className="bezel__sheen" aria-hidden="true" />
        <div className="chat__head">
          <span className="eyebrow">Drafts — chief of staff writes, you approve</span>
        </div>

        <div className="draft__make">
          <div className="chat__input">
            <input
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && generate()}
              placeholder="Draft a reply to the investor / a Slack update on the pricing change…"
            />
            <select className="draft__chan" value={channel} onChange={(e) => setChannel(e.target.value)}>
              <option value="email">email</option>
              <option value="slack">slack</option>
            </select>
            <button className="btn btn--primary group" onClick={generate} disabled={busy}>
              {busy ? 'Drafting…' : 'Draft'}
              <span className="btn__icon" aria-hidden="true">↗</span>
            </button>
          </div>
        </div>

        <div className="draft__list">
          {list.length === 0 && <p className="chat__empty">No drafts waiting. Ask for one above.</p>}
          {list.map((d) => (
            <div key={d.id} className="draft__card">
              <div className="draft__meta">
                <span className="draft__chip">{d.channel}</span>
                {d.recipient && <span className="draft__to">to {d.recipient}</span>}
              </div>
              {d.subject && d.subject !== 'N/A' && <p className="draft__subject">{d.subject}</p>}
              <p className="draft__body">{d.body}</p>
              <div className="draft__actions">
                <button className="btn btn--primary group" onClick={() => act(d.id, 'approve')}>
                  Approve &amp; send
                  <span className="btn__icon" aria-hidden="true">↗</span>
                </button>
                <button className="btn btn--ghost" onClick={() => act(d.id, 'discard')}>Discard</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Drafts;
