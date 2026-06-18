import React, { useState } from 'react';
import { API_BASE } from '../config';
import { isDemoFounder } from '../demo';
import '../styles/chat.css';

interface Msg {
  role: 'user' | 'assistant';
  content: string;
}

const DEMO_REPLY =
  "I'm your chief of staff. In the live product I'd pull your Stripe, Slack, email, calendar and Granola notes to answer this and draft what you need — for your approval. (Demo mode: backend not connected.)";

const ChatPanel: React.FC<{ founderId: string }> = ({ founderId }) => {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const demo = isDemoFounder(founderId);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setMsgs((m) => [...m, { role: 'user', content: text }]);
    setInput('');

    if (demo) {
      setMsgs((m) => [...m, { role: 'assistant', content: DEMO_REPLY }]);
      return;
    }
    setBusy(true);
    try {
      const r = await fetch(`${API_BASE}/founders/${founderId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setMsgs((m) => [...m, { role: 'assistant', content: data.reply || '(no reply)' }]);
    } catch {
      setMsgs((m) => [
        ...m,
        { role: 'assistant', content: 'Assistant unavailable — the backend isn’t running.' }
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bezel chat">
      <div className="bezel__core">
        <span className="bezel__sheen" aria-hidden="true" />
        <div className="chat__head">
          <span className="eyebrow">Ask your chief of staff</span>
        </div>

        <div className="chat__log">
          {msgs.length === 0 && (
            <p className="chat__empty">
              Ask anything — "what's our churn story for the board?", "draft a reply to the
              Sequoia partner", "push back on my Q3 hiring plan".
            </p>
          )}
          {msgs.map((m, i) => (
            <div key={i} className={`chat__msg chat__msg--${m.role}`}>
              {m.content}
            </div>
          ))}
          {busy && <div className="chat__msg chat__msg--assistant chat__typing">thinking…</div>}
        </div>

        <div className="chat__input">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && send()}
            placeholder="Message your chief of staff…"
          />
          <button className="btn btn--primary group" onClick={send} disabled={busy}>
            Send
            <span className="btn__icon" aria-hidden="true">↗</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatPanel;
