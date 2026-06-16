# AI Chief of Staff for Founders — SaaS Product Doctrine

This document defines what we're building, why, and how we know it's done.

---

## Objective

A real-time decision intelligence platform that monitors a founder's business 24/7 and surfaces only the decisions that matter, enabling founders to make better decisions in 15–20 minutes instead of 2–3 hours.

**Target market:** SaaS and e-commerce founders with back-to-back calls and long days who can't afford context-switching.

---

## User & Context

**Primary persona:**
- SaaS or e-commerce founder (bootstrapped or Series A)
- Spends most of day in back-to-back calls and meetings
- Checks email/Slack sporadically between meetings
- Decision-fatigue: spends 2–3 hours assembling context for a single decision
- Values speed and accuracy (wrong decisions cost customers, revenue, momentum)

**Usage scenario:**
- Founder in a meeting gets a Slack notification: "Revenue alert: MRR dropped $2K"
- Without leaving the meeting, they click the link and see:
  - What happened (revenue drop details)
  - Why it matters (compared to baseline)
  - What happened last time (historical precedent)
  - What to do next (suggested actions)
- They decide: pause ads, delegate investigation to CFO, or dismiss if false alarm
- They mark as "Delegated" and continue meeting

**Pain point solved:**
Founders waste 2–3 hours per decision gathering context from email, Slack, calendar, metrics dashboards, and team members. Meanwhile, time-sensitive decisions (customer churn, revenue drops, key hires) are delayed. This product cuts decision context-assembly time by 80–90%, so founders spend time *deciding*, not *researching*.

**Reputation is everything:** A single false alert that wastes a founder's time erodes trust. The product must have high alert accuracy (80%+) or it becomes noise.

---

## Must-Have Requirements

### Data Sources to Monitor

The system continuously monitors these 4 data sources:

1. **Revenue & MRR** (Stripe, payment processor)
   - Watch for: MRR drops >5%, churn acceleration, failed payment retries
   - Update frequency: Every 5 minutes

2. **Customer Churn Signals** (support tickets, cancellations, NPS, customer feedback)
   - Watch for: Customer cancellations, angry support tickets, NPS drops, churn keywords ("canceling", "switching", "too expensive")
   - Update frequency: Every 5 minutes

3. **Team Communication** (Slack channels, email threads)
   - Watch for: Escalations, conflicts, urgent customer/investor issues, team morale signals
   - Update frequency: Every 5 minutes

4. **Product Metrics** (dashboards, key KPIs: signup rate, activation, retention)
   - Watch for: Sudden drops in KPIs, anomalies vs. baseline
   - Update frequency: Every 5 minutes

### Urgency Triggers (What Gets an Alert)

Real-time alerts surface when ANY of these conditions trigger:

1. **Customer Churn Signal**
   - High-value customer cancels
   - Angry customer emails or support tickets
   - NPS score drops >15 points
   - Trigger: Within 2 minutes of event

2. **Revenue Anomaly**
   - MRR drops >5% in a day
   - Churn rate spikes >2x baseline
   - Failed payment rate spikes
   - Trigger: Within 5 minutes of event

3. **Key Investor/Customer Reaching Out**
   - Email/Slack from known investor, customer, or strategic partner
   - Trigger: Within 1 minute of message arrival

4. **Team Conflict Surfacing in Slack**
   - Escalation messages (caps lock, multiple exclamation marks)
   - Conflict keywords (disagree, blocked, stuck, urgent)
   - High-priority Slack channel activity
   - Trigger: Within 2 minutes of message

5. **Competitor Move** (optional, v1)
   - Competitor pricing change, feature launch, funding announcement
   - Trigger: Daily scan, alert within 24 hours

### Alert Anatomy

Every alert delivered to the founder includes:

```
📊 ALERT: Revenue Drop
---
WHAT HAPPENED:
  MRR dropped $2,000 (from $18K to $16K) in last 24 hours
  Churn: 3 customers canceled (vs. 0.5 avg/day)

WHY IT MATTERS:
  $24K annualized revenue at risk
  Could indicate pricing sensitivity or product issue

WHAT HAPPENED LAST TIME:
  3 months ago: Similar $2K drop
  Root cause: Competitor pricing change
  Action taken: Paused ads, focused on retention
  Outcome: Recovered to $20K in 2 weeks

WHAT TO DO NEXT:
  1. Check which customers churned (are they price-sensitive?)
  2. Review competitor pricing
  3. Pause high-CAC channels if needed
  4. Consider retention outreach

NEXT DECISION:
  Should we pause ads and focus on retention?
  [DECIDE]  [DELEGATE]  [DISMISS]
```

### Dashboard Actions

Founders can take 4 actions on each alert:

1. **Decide** — Mark as "I'm handling this" (tracks decision, logs outcome later)
2. **Delegate** — "I'm assigning to [team member]" (sends delegate notification)
3. **Dismiss** — "This isn't urgent / false alarm" (feedback for ML model)
4. **View History** — See similar past decisions and their outcomes

### Integrations (Required for v1)

| Integration | Purpose | Permissions | Sync Interval |
|---|---|---|---|
| **Stripe** | Revenue, churn, failed payments | Read-only API | Every 5 min |
| **Slack** | Team communication, escalations | Read channels, post alerts | Real-time |
| **Email** | Inbound from customers, investors | Read inbox (imap/api) | Every 5 min |
| **Google Calendar** | Context on founder's meetings, stakeholders | Read-only | Every 10 min |
| **Salesforce/HubSpot** (optional) | Customer context, deals, notes | Read-only API | Every 10 min |

---

## Constraints

| Constraint | Details |
|---|---|
| **Timeline** | As long as it takes (no hard deadline) |
| **Team** | 3 people |
| **Budget** | TBD (infrastructure, API costs) |
| **Platforms** | Web + responsive mobile (landscape mode must be readable without horizontal scroll) |
| **Tech Stack** | Open; suggestions welcome |
| **Hosting** | Two-phase (see Deployment Model below): multi-tenant SaaS for POC/testing → **self-hosted single-tenant** ("data stays on the founder's own servers") for production |
| **Data Privacy** | Founder credentials never stored in logs; sensitive data encrypted. In production, founder data must never leave the founder's own infrastructure |

---

## Deployment Model

The hosting model changes between phases — this is a deliberate decision, not drift.

### Phase 1 — POC / Testing: Multi-tenant SaaS
- We host everything centrally (our cloud: backend, PostgreSQL+pgvector, frontend).
- Founders sign up at a URL, connect tools via OAuth. Fast to ship, easy to iterate.
- **Trade-off:** founder data lives in *our* database. Acceptable for POC and design partners who've agreed to it; **not** acceptable for the production offering.

### Phase 2 — Production: Self-hosted, single-tenant ("data stays on the founder's own servers")
- Each founder runs their **own isolated instance** on **their** infrastructure (their AWS/GCP account or on-prem).
- Founder data — signals, alerts, decisions, semantic memory, OAuth tokens — **never leaves their environment**. We never hold it.
- This is the core differentiator and privacy promise; it mirrors Dan Martell's "Apex" positioning.

**What this requires (Phase 2 engineering, not yet built):**
- Packaged deployable artifact: Docker Compose / Helm chart / Terraform module the founder (or our installer) runs in their account.
- Per-instance configuration & secrets (LLM keys, integration tokens) owned by the founder.
- Licensing / activation that works without us seeing their data (e.g. signed license key, telemetry strictly opt-in and PII-free).
- Update/release mechanism for pushing new versions to many isolated instances.
- LLM inference decision: **RESOLVED** → hybrid, default to BYO cloud keys, with a config-only switch to a fully-local OpenAI-compatible model for the strict "data never leaves" tier. Decision record: `app/docs/llm-inference.md`. Implemented in `app/backend/coordinator.py` (env-driven model chain, `LLM_MODE=cloud|local`).

**Phase-2 packaging (drafted):** `app/deploy/` contains the self-hosted stack — `docker-compose.prod.yml` (db + backend + nginx-served frontend, optional local `ollama`), `.env.example`, `nginx.conf` (same-origin API proxy), `frontend.Dockerfile`, and `README.md` install guide. Frontend API base is now env-configurable (`REACT_APP_API_URL`, defaults to same-origin) so it serves cleanly behind one origin.

**Implication for Phase-1 build:** keep the app single-tenant-clean — no cross-tenant queries, all data scoped by founder, config/secrets injected via env — so the same codebase can deploy as one isolated instance without a rewrite. (The current build already scopes by `founder_id` and injects secrets via env, which is compatible.)

---

## Messiest Edge Cases (How v1 Handles Them)

### 1. Conflicting Data Signals
**Scenario:** Stripe shows revenue is stable, but Slack is full of angry customer complaints. Which signal is urgent?

**How v1 handles it:**
- Surface the Slack signal (immediate threat)
- Show Stripe data as context ("But revenue is still up")
- Include a **data freshness indicator**: "Stripe data last updated 3 minutes ago" so founder knows if Stripe is stale
- Require >1 signal before surfacing: don't alert on Slack escalation alone; require corroborating signal (customer cancellation, support tickets)

### 2. Alert Noise (False Positives)
**Scenario:** System sends 50 alerts/day, founder ignores all of them. Product dies.

**How v1 handles it:**
- **High confidence threshold**: Require ≥2 independent signals before surfacing an alert (not just 1 data source)
  - Revenue + Churn trigger = alert
  - Revenue alone = no alert (could be API lag, accounting quirk)
- **Track alert accuracy**: Log what founder does (Decide/Delegate/Dismiss) and which alerts lead to actual decisions
- **Feedback loop**: If founder dismisses >50% of alerts, suppress the low-confidence signal

### 3. Stale Integrations
**Scenario:** Email hasn't synced in 6 hours, Stripe data is 2 hours old. Are the alerts based on stale data?

**How v1 handles it:**
- **Freshness indicators** on every alert:
  - "Stripe: 3 min old ✓"
  - "Email: 45 min old ⚠️"
  - "Slack: Real-time ✓"
- **Fail gracefully**: If an integration is down (Stripe API timeout), system still pulls from other sources
- **Don't suppress alerts**: If Stripe is down but Slack shows urgent escalation, surface it (with freshness warning)

### 4. Multi-Company Founders
**Scenario:** Founder runs 2 companies. Should alerts be per-company or aggregated?

**How v1 handles it:**
- **One account = one company** for v1
- If founder has multiple companies, they need separate accounts/logins
- Revisit for v2 when multi-tenancy is feasible

---

## Explicitly Out of Scope (v1)

These features are **not** in v1; they're v2+ targets:

- ❌ **Autonomous execution** — The AI recommends decisions; founder always approves. No emails sent without draft review, no calendar invites sent, no money moved. (Even if founder says "just do it," system surfaces for review first.)

- ❌ **Team/Organization visibility** — v1 alerts only the founder. Not a team collaboration tool (yet). No "assign to Jane" in v1; only "Delegate" to track.

- ❌ **Predictive alerts** — v1 is reactive: "This happened, here's context." NOT predictive: "Revenue might drop in 2 weeks based on trend."

- ❌ **Custom rule-building** — Founders can't create custom alert rules yet. Only founder's alerts, not "notify me when X happens."

- ❌ **Native mobile app** — Responsive web only. No native iOS/Android app yet.

- ❌ **Third-party API** — Other tools can't call your API to integrate alerts. Founder-facing only.

- ❌ **Historical trends / analytics** — No "revenue declined 15% over 3 weeks" or "we've been making worse decisions lately." Just current-state alerts.

---

## Success Metrics (How We Know v1 Works)

| Metric | Target | How We Measure |
|---|---|---|
| **Decision Impact** | 80% of founders report the AI helped them avoid a bad decision or save time | Post-decision survey: "Did this alert help?" |
| **Daily Adoption** | 80% of paying founders use the dashboard daily | Product analytics: DAU / paying users |
| **Revenue** | $5K MRR by end of year | Stripe, billing dashboard |
| **Time Saved** | Decision-making time drops from 2–3 hours to 15–20 minutes (80–90% reduction) | Founder interview/survey: "How long do decisions take now?" |
| **Alert Accuracy** | 80% of alerts result in founder action within 24 hours | Product analytics: % of alerts where founder clicks Decide/Delegate (not Dismiss) |

---

## Definition of Done

A build is **done and correct** when all of the following are true:

- [ ] **Real-time alerts arrive in Slack** within 30 seconds of trigger event (revenue drop >5%, churn, investor email, team escalation)
- [ ] **Alert content is complete** — each alert shows: what happened, why it matters, historical precedent, next steps, and data freshness
- [ ] **Dashboard loads in <2 seconds** and displays all active alerts with full context
- [ ] **Mobile landscape readability** — dashboard is readable on iPhone 12 landscape without horizontal scroll
- [ ] **Integrations are live and syncing** — Stripe/Slack/Email/Calendar data syncs every 5 minutes (max 10-min lag)
- [ ] **Alert accuracy >80%** — in testing, >80% of surfaced alerts are relevant to founder's business (not noise)
- [ ] **Failed integrations degrade gracefully** — if one integration is down (Stripe timeout), system still pulls from others and alerts aren't lost
- [ ] **Founder can track decisions** — can mark alerts as Decide/Delegate/Dismiss and see history of past decisions
- [ ] **No critical events missed** — customer churn signals and revenue anomalies never fail to trigger
- [ ] **Data privacy enforced** — founder credentials and sensitive data are never logged or exposed in UI/API responses

---

## Notes & Assumptions

**Open questions for the team:**
1. How should the system weight conflicting signals? (Revenue stable but Slack angry = which takes priority?)
2. Should the AI proactively surface opportunities ("You haven't heard from sales in 3 days, might want to check in") or only reactive alerts?
3. For pricing: per-month subscription ($X/month) or usage-based?

**Tech recommendations (to be confirmed):**
- **Orchestration:** LangGraph for stateful alert workflows
- **LLM integration:** Claude API with circular fallback (Claude → GPT-4 → Claude Sonnet) + exponential backoff
- **Memory:** PostgreSQL + pgvector for semantic memory (remember past decisions, precedents)
- **Hosting:** AWS/GCP Cloud Run (serverless, scales with alert volume)
- **Frontend:** React (web) + responsive design (mobile landscape support)

**Assumptions:**
- Founders will integrate via OAuth (Stripe, Google, Slack) — no manual credential entry
- Alert latency of 30 seconds is acceptable (not <5 sec)
- Founders are in US timezones (no global timezone complexity in v1)

---

**Doctrine version:** 1.0  
**Last updated:** 2026-06-16  
**Status:** Ready for implementation
