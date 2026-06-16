import React, { useEffect, useState, useCallback, useRef } from 'react';
import AlertCard from '../components/AlertCard';
import DecisionHistory from '../components/DecisionHistory';
import PulsePanel from '../components/PulsePanel';
import Tilt from '../components/Tilt';
import { API_BASE } from '../config';
import { DEMO_ALERTS, isDemoFounder } from '../demo';
import '../styles/Dashboard.css';
import '../styles/fx.css';

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

interface DashboardProps {
  founderId: string;
}

const Dashboard: React.FC<DashboardProps> = ({ founderId }) => {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [showHistory, setShowHistory] = useState(false);
  const [theme, setTheme] = useState<'dark' | 'light'>(
    () => (document.documentElement.getAttribute('data-theme') as 'dark' | 'light') || 'dark'
  );
  const rootRef = useRef<HTMLDivElement>(null);
  const demo = isDemoFounder(founderId);

  // Apply + persist theme at the document root so every token cascades.
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem('cos-theme', theme);
    } catch (e) {
      /* ignore */
    }
  }, [theme]);

  const fetchAlerts = useCallback(async () => {
    // Demo founder: load bundled data directly, never touch the network.
    if (isDemoFounder(founderId)) {
      setAlerts(DEMO_ALERTS as Alert[]);
      setLoading(false);
      return;
    }
    try {
      const response = await fetch(
        `${API_BASE}/founders/${founderId}/alerts?status=active`
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setAlerts(await response.json());
    } catch (error) {
      console.error('Failed to fetch alerts:', error);
    } finally {
      setLoading(false);
    }
  }, [founderId]);

  useEffect(() => {
    fetchAlerts();
    // Demo mode is static (no backend) — don't poll, so optimistic actions stick.
    if (demo) return;
    const interval = setInterval(fetchAlerts, 5000);
    return () => clearInterval(interval);
  }, [fetchAlerts, demo]);

  // Entrance animation is pure CSS (.reveal keyframes) — no JS/observer,
  // so a re-render or timing race can never leave the page blank.

  // Optimistically remove the acted alert; POST to the API; refetch unless demo.
  const act = async (alertId: string, path: string, body: object, label: string) => {
    setAlerts((prev) => prev.filter((a) => a.id !== alertId)); // optimistic
    if (demo) return; // demo is local-only; nothing to POST
    try {
      await fetch(`${API_BASE}/founders/${founderId}/alerts/${alertId}/${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      await fetchAlerts();
    } catch (error) {
      console.error(`Failed to ${label}:`, error);
    }
  };

  const handleDecision = (alertId: string, decisionText: string) =>
    act(alertId, 'decide', { decision_text: decisionText }, 'record decision');
  const handleDelegate = (alertId: string, delegatedTo: string) =>
    act(alertId, 'delegate', { delegated_to: delegatedTo }, 'delegate');

  const handleDismiss = (alertId: string, reason: string) =>
    act(alertId, 'dismiss', { reason }, 'dismiss alert');

  // Background mesh parallax — pointer position drives --px/--py on the root.
  const paraFrame = useRef<number | null>(null);
  const onParallax = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = rootRef.current;
    if (!el) return;
    const px = (e.clientX / window.innerWidth - 0.5) * 2;
    const py = (e.clientY / window.innerHeight - 0.5) * 2;
    if (paraFrame.current) cancelAnimationFrame(paraFrame.current);
    paraFrame.current = requestAnimationFrame(() => {
      el.style.setProperty('--px', px.toFixed(3));
      el.style.setProperty('--py', py.toFixed(3));
    });
  };

  const avgConfidence = alerts.length
    ? Math.round(
        (alerts.reduce((s, a) => s + (a.confidence || 0), 0) / alerts.length) * 100
      )
    : 0;
  const sourceCount = alerts.length
    ? Object.keys(alerts[0].data_freshness || {}).length
    : 4;

  return (
    <div className="cos" ref={rootRef} onMouseMove={onParallax}>
      {/* Ambient mesh background */}
      <div className="cos__mesh" aria-hidden="true">
        <span className="orb orb--violet" />
        <span className="orb orb--emerald" />
        <span className="orb orb--indigo" />
      </div>
      <div className="cos__grain" aria-hidden="true" />

      {/* Fluid-island header */}
      <header className="island reveal">
        <div className="island__brand">
          <span className="island__mark" aria-hidden="true" />
          <span className="island__name">dCernment</span>
        </div>
        <div className="island__right">
          {demo && <span className="demo-pill">Demo data</span>}
          <span className="status-pill" title="Monitoring active">
            <span className="status-pill__dot" />
            Monitoring · {sourceCount} sources
          </span>

          <button
            className="theme-toggle"
            onClick={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
            aria-label="Toggle light and dark theme"
            title="Toggle theme"
          >
            <span className="theme-toggle__ico theme-toggle__ico--sun" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round">
                <circle cx="12" cy="12" r="4.2" />
                <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.2 5.2l1.4 1.4M17.4 17.4l1.4 1.4M18.8 5.2l-1.4 1.4M6.6 17.4l-1.4 1.4" />
              </svg>
            </span>
            <span className="theme-toggle__ico theme-toggle__ico--moon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 14.5A8 8 0 1 1 9.5 4a6.2 6.2 0 0 0 10.5 10.5z" />
              </svg>
            </span>
            <span className="theme-toggle__thumb" aria-hidden="true" />
          </button>

          <button
            className="ghost-pill"
            onClick={() => setShowHistory((v) => !v)}
          >
            {showHistory ? 'Hide history' : 'Decision history'}
            <span className="ghost-pill__icon" aria-hidden="true">
              {showHistory ? '×' : '↗'}
            </span>
          </button>
        </div>
      </header>

      <main className="cos__main">
        {/* Section intro */}
        <section className="intro reveal">
          <span className="eyebrow">Real-time decision intelligence</span>
          <h1 className="intro__title">
            What needs <em>you</em> today
          </h1>
          <p className="intro__sub">
            We watched everything overnight. Only the decisions that move the
            business made it here.
          </p>

          <div className="stat-strip">
            <Tilt className="stat" max={8} lift={4}>
              <span className="stat__num">{loading ? '—' : alerts.length}</span>
              <span className="stat__label">Active decisions</span>
            </Tilt>
            <Tilt className="stat" max={8} lift={4}>
              <span className="stat__num">{loading ? '—' : `${avgConfidence}%`}</span>
              <span className="stat__label">Avg. confidence</span>
            </Tilt>
            <Tilt className="stat" max={8} lift={4}>
              <span className="stat__num">{sourceCount}</span>
              <span className="stat__label">Live sources</span>
            </Tilt>
          </div>
        </section>

        {!loading && alerts.length > 0 && (
          <div className="reveal pulse-wrap">
            <PulsePanel alerts={alerts} />
          </div>
        )}

        {showHistory && (
          <div className="reveal">
            <DecisionHistory founderId={founderId} />
          </div>
        )}

        <section className="feed">
          {loading ? (
            <div className="feed__loading reveal">Listening to your business…</div>
          ) : alerts.length === 0 ? (
            <div className="empty reveal">
              <span className="empty__glyph" aria-hidden="true" />
              <h3>You're clear</h3>
              <p>No decisions need you right now. We'll surface the next one the moment it matters.</p>
            </div>
          ) : (
            alerts.map((alert, i) => (
              <div
                key={alert.id}
                className="reveal"
                style={{ animationDelay: `${Math.min(i * 90, 360)}ms` }}
              >
                <AlertCard
                  alert={alert}
                  index={i}
                  onDecide={(text) => handleDecision(alert.id, text)}
                  onDelegate={(to) => handleDelegate(alert.id, to)}
                  onDismiss={(reason) => handleDismiss(alert.id, reason)}
                />
              </div>
            ))
          )}
        </section>

        <footer className="cos__footer reveal">
          <span className="cos__footer-dot" />
          Syncing every 5 minutes · last updated {new Date().toLocaleTimeString()}
        </footer>
      </main>
    </div>
  );
};

export default Dashboard;
