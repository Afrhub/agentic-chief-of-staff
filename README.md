# dCernment — SaaS Platform

A real-time decision intelligence platform that monitors a founder's business 24/7 and surfaces only the decisions that matter.

## Build Status

**Iteration 1** — Core architecture, alert orchestration, integrations, and dashboard UI.

## Quick Start

### Local Development (Docker Compose)

```bash
# Set environment variables
export CLAUDE_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export SLACK_BOT_TOKEN=xoxb-...
export STRIPE_API_KEY=sk_live_...
export GOOGLE_CLIENT_ID=...
export GOOGLE_CLIENT_SECRET=...

# Start all services
docker-compose up

# Backend: http://localhost:8000
# Frontend: http://localhost:3000
# Database: postgres://localhost:5432
```

### Manual Setup

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL=postgresql://localhost/chief_of_staff
export CLAUDE_API_KEY=sk-ant-...

python main.py
```

**Frontend:**
```bash
cd frontend
npm install
npm start
```

**Database:**
```bash
# Create PostgreSQL database with pgvector extension
psql -U postgres
CREATE DATABASE chief_of_staff;
\c chief_of_staff
CREATE EXTENSION vector;
```

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/health` | Health check |
| `POST` | `/founders/{id}/alerts` | Create alert from signals |
| `GET` | `/founders/{id}/alerts` | Fetch active alerts |
| `POST` | `/founders/{id}/alerts/{id}/decide` | Mark as decided |
| `POST` | `/founders/{id}/alerts/{id}/delegate` | Mark as delegated |
| `POST` | `/founders/{id}/alerts/{id}/dismiss` | Mark as dismissed |
| `GET` | `/founders/{id}/decisions` | Fetch decision history |

## Architecture

```
┌─────────────────────────────────────────┐
│         Founder Input (Slack API)       │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│      FastAPI + LangGraph Coordinator    │
│  - Multi-signal analysis                │
│  - High-confidence threshold (≥2)       │
│  - LLM synthesis (Claude + fallback)    │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│   PostgreSQL + pgvector Memory Layer    │
│  - Checkpoints                          │
│  - Semantic memory (past decisions)     │
│  - Decision tracking                    │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│      React Dashboard (Web + Mobile)     │
│  - Alert display with full context      │
│  - Decide/Delegate/Dismiss actions      │
│  - Decision history                     │
└─────────────────────────────────────────┘
```

## Integration Adapters

- **Stripe:** Revenue, churn, failed payments (every 5 min)
- **Slack:** Team communication, escalations (real-time webhook)
- **Email:** Customer/investor inbound (every 5 min via IMAP)
- **Google Calendar:** Meeting context, free blocks (every 10 min)
- **Salesforce/HubSpot:** Customer data (optional, every 10 min)

## Doctrine Compliance

See [/doctrine.md](doctrine.md) for full spec.

**Definition of Done Checklist:**
- [ ] Real-time alerts in Slack (<30 sec latency)
- [ ] Alert content complete (what, why, next steps, precedents)
- [ ] Dashboard loads <2 sec
- [ ] Mobile landscape readable (no horiz scroll)
- [ ] Integrations syncing (5-10 min intervals)
- [ ] Alert accuracy >80% (80%+ user action rate)
- [ ] Graceful degradation (failed integrations don't suppress alerts)
- [ ] Founder can track decisions (Decide/Delegate/Dismiss + history)
- [ ] No critical events missed
- [ ] Data privacy enforced (credentials encrypted, never logged)

## Deployment (Production)

### Cloud Run (GCP)

```bash
# Build and push Docker image
gcloud builds submit --tag gcr.io/YOUR_PROJECT/chief-of-staff

# Deploy
gcloud run deploy chief-of-staff \
  --image gcr.io/YOUR_PROJECT/chief-of-staff \
  --platform managed \
  --region us-central1 \
  --memory 4Gi \
  --cpu 2 \
  --set-env-vars DATABASE_URL=$DB_URL,CLAUDE_API_KEY=$KEY
```

### AWS (ECS + Cloud Run alternative)

```bash
# Push to ECR
aws ecr get-login-password | docker login --username AWS --password-stdin $ACCOUNT.dkr.ecr.$REGION.amazonaws.com
docker tag chief-of-staff:latest $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/chief-of-staff:latest
docker push $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/chief-of-staff:latest

# Deploy via ECS task definition
```

### Environment Variables

Required:
- `DATABASE_URL` — PostgreSQL connection string with pgvector
- `CLAUDE_API_KEY` — Anthropic API key
- `OPENAI_API_KEY` — OpenAI API key (fallback)
- `SLACK_BOT_TOKEN` — Slack bot token (post alerts)
- `STRIPE_API_KEY` — Stripe API key (read revenue)
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — Gmail/Calendar OAuth

Optional:
- `SALESFORCE_CLIENT_ID` / `SALESFORCE_CLIENT_SECRET` — Salesforce integration

## Testing

```bash
# Backend unit tests
cd backend
pytest tests/

# Frontend tests
cd frontend
npm test

# Integration tests
docker-compose up
pytest tests/integration/
```

## Known Limitations (v1)

- ❌ No autonomous execution (AI recommends, founder approves)
- ❌ No team/org visibility (founder-only alerts)
- ❌ No predictive alerts (reactive only)
- ❌ No custom rule-building
- ❌ No native mobile app (responsive web only)
- ❌ No third-party API
- ❌ No historical trends/analytics

See [/doctrine.md](doctrine.md) for v2 roadmap.

## Monitoring

**Metrics to track:**
- Alert latency (should be <30 sec)
- Alert accuracy (% dismissed by founder)
- Daily active usage (% founders using daily)
- Decision impact (% reporting it helped)
- Integration sync health (% successful syncs)

**Logging:**
- All LLM calls logged (for debugging)
- Alert surface/suppress decisions logged
- Integration errors logged (with retry backoff)

## Contributing

See [/doctrine.md](doctrine.md) for spec-driven development guidelines.

## License

Proprietary — dCernment
