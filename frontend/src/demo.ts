// Self-contained demo data so the app renders a full, realistic dashboard
// without a backend (e.g. a static deploy or first visit). Used only as a
// fallback when the API is unreachable for the demo founder.

export const DEMO_FOUNDER_ID = 'demo-founder';

export const isDemoFounder = (id: string) => id === DEMO_FOUNDER_ID;

const minsAgo = (m: number) => new Date(Date.now() - m * 60 * 1000).toISOString();
const daysAgo = (d: number) => new Date(Date.now() - d * 24 * 3600 * 1000).toISOString();

export const DEMO_ALERTS = [
  {
    id: 'a1',
    type: 'revenue_anomaly',
    title: 'Decision: Should we pause ads and focus on retention?',
    what_happened:
      'MRR dropped $2,000 (from $18K to $16K) in the last 24 hours. 3 customers canceled vs a 0.5/day baseline. Two cancellations cited pricing.',
    why_it_matters:
      '$24K of annualized revenue is at risk. The clustering with pricing complaints in Slack suggests this is pricing sensitivity, not random churn.',
    what_to_do_next:
      '1. Pull the 3 churned accounts — are they all on the new pricing tier?\n2. Cross-check the #customers Slack thread on the price change.\n3. Pause high-CAC paid channels until retention stabilizes.\n4. Draft retention outreach to at-risk accounts.',
    next_decision: 'Should we pause ads and focus on retention this week?',
    options: [
      'Pause paid ads and redirect spend to retention outreach',
      'Hold spend and run a pricing win-back to the 3 churned accounts',
      'Wait one week and re-measure before acting'
    ],
    precedent_context:
      '3 months ago a similar $2K MRR drop traced to a competitor price cut. You paused ads and ran retention outreach; MRR recovered to $20K within 2 weeks.',
    trend: [18.2, 18.4, 18.1, 18.5, 18.3, 18.6, 18.2, 18.0, 17.9, 18.1, 17.7, 17.3, 16.5, 16.0],
    data_freshness: {
      stripe: '2 min old ✓',
      slack: 'real-time ✓',
      email: '4 min old ✓',
      calendar: '8 min old ⚠️'
    },
    confidence: 0.88,
    triggered_at: minsAgo(6)
  },
  {
    id: 'a2',
    type: 'investor_contact',
    title: 'Decision: How fast do we respond to the Sequoia partner?',
    what_happened:
      'Inbound email from a Sequoia partner (known investor) requesting an updated metrics deck before Friday, alongside a calendar hold for Thursday.',
    why_it_matters:
      'Time-sensitive investor relationship. A slow or unprepared response ahead of a fundraise window is hard to recover from.',
    what_to_do_next:
      "1. Confirm Thursday availability.\n2. Assemble the latest metrics deck (MRR, retention, runway).\n3. Decide what to disclose given this week's revenue dip.",
    next_decision: 'Reply today with the deck, or wait until churn is diagnosed?',
    options: [
      'Reply today with the current deck and flag the dip',
      'Wait until the churn is diagnosed, then send a fuller picture',
      'Delegate the deck prep to the CFO and reply Thursday'
    ],
    precedent_context: null,
    data_freshness: {
      stripe: '2 min old ✓',
      slack: 'real-time ✓',
      email: '4 min old ✓',
      calendar: '8 min old ⚠️'
    },
    confidence: 0.91,
    triggered_at: minsAgo(22)
  }
];

// The agent fleet — human identities (mirrors backend/agents/identities.py).
// Rendered by the Team view; also the fallback if /agents/fleet is unreachable.
export const DEMO_FLEET = [
  { axis: 'money', name: 'James', role: 'Finance Director', traits: ['numbers-first', 'calm under pressure', 'conservative', 'no vanity metrics'], watches: 'MRR, churn-driven revenue loss, failed-payment spikes, runway', model: 'claude-haiku-4-5', source: 'stripe' },
  { axis: 'customers', name: 'Sofia', role: 'Head of Customer Success', traits: ['empathetic', 'data-driven', 'retention-obsessed', 'hears churn early'], watches: 'cancellations, pre-churn behaviour, health-score and NPS drops', model: 'claude-haiku-4-5', source: 'scorecard' },
  { axis: 'comms', name: 'Marcus', role: 'Chief of Staff (gatekeeper)', traits: ['discerning', 'protects your attention', 'politically astute', 'fast triage'], watches: 'investor/VIP inbound, time-sensitive external asks, team friction', model: 'claude-sonnet-4-6', source: 'scorecard' },
  { axis: 'meetings', name: 'Priya', role: 'Executive Assistant', traits: ['meticulous', 'never drops a commitment', 'deadline-aware', 'reads subtext'], watches: 'commitments made, deadlines, risks and competitor mentions in meetings', model: 'claude-sonnet-4-6', source: 'granola' },
  { axis: 'ops', name: 'David', role: 'Head of Operations', traits: ['reliability-first', 'process-minded', 'watches quiet failures', 'unflappable'], watches: 'uptime/incidents, hiring and people-runway, process breakdowns', model: 'claude-haiku-4-5', source: 'scorecard' }
];

export const DEMO_DECISIONS = [
  {
    id: 'd1',
    type: 'delegate',
    decision_text: 'Delegated to CFO: investigate failed-payment spike',
    made_at: daysAgo(1),
    outcome: 'Resolved — dunning email misconfigured',
    impact: 'positive'
  },
  {
    id: 'd2',
    type: 'decide',
    decision_text: 'Held Q3 hiring until pipeline recovers',
    made_at: daysAgo(3),
    outcome: undefined,
    impact: undefined
  }
];
