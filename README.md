# CMO Agent System - Webhook Gateway

FastAPI gateway exposing Python automation scripts via HTTP endpoints. Enables Slack commands, cron jobs, and external triggers to run analytics, TikTok scraping, cold email automation, and content generation.

## Quick Start

```bash
# Install dependencies
cd /mnt/e/Dev2/CMO_Agent_System
pip install -r gateway/requirements.txt

# Set environment variables
export CMO_GATEWAY_API_KEY=$(openssl rand -hex 32)
export CMO_GATEWAY_DEBUG=true

# Run locally
uvicorn gateway.main:app --reload --port 8088

# Or use the module entry point
python -m gateway.main
```

## Quick demo (no private routers)

The repo ships a self-contained demo path so you can exercise the async job
flow without any client config, secrets, or private routers. It uses a mock
"summarize a topic" job that sleeps a few seconds and returns clearly-labeled
fake data (a hypothetical SaaS called **PingDesk**).

```bash
# 1. Start the server in debug mode with any API key
export CMO_GATEWAY_API_KEY=demo-key-123
export CMO_GATEWAY_DEBUG=true
uvicorn gateway.main:app --reload --port 8088

# 2. Submit a demo job (returns a job_id immediately)
curl -X POST http://localhost:8088/demo/job \
  -H "X-API-Key: demo-key-123" \
  -H "Content-Type: application/json" \
  -d '{"topic": "how to answer the phone after hours", "duration_seconds": 3}'
# → {"job_id": "abc12345", "status": "pending", "message": "Demo summarize-topic job queued"}

# 3. Watch it move pending → running → completed
curl http://localhost:8088/jobs -H "X-API-Key: demo-key-123"
curl http://localhost:8088/jobs/abc12345 -H "X-API-Key: demo-key-123"
```

Then open the **jobs dashboard** in a browser:

```
http://localhost:8088/static/dashboard.html
```

Paste your API key into the dashboard, submit a job, and watch the live list
(auto-refreshes every 2s). Click any row to see its status timeline and the
fake structured summary. Everything is local — no network calls, no secrets.

| Demo file | Purpose |
|-----------|---------|
| `demo/sample_job.py` | Mock async job (`summarize_topic`) — sleeps, returns fake summary |
| `routers/demo.py` | `POST /demo/job` — submits the sample job into the shared queue |
| `static/dashboard.html` | Single-page jobs dashboard (pure HTML/JS) |

## Configuration

Add to `scripts/.env`:

```bash
CMO_GATEWAY_API_KEY=<your-32-char-key>
CMO_GATEWAY_PORT=8088
CMO_GATEWAY_HOST=0.0.0.0
CMO_GATEWAY_DEBUG=false
```

## API Endpoints

### Health (No Auth)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/` | GET | API info |

### Analytics (Sync)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhooks/analytics/summary` | POST | Executive summary |
| `/webhooks/analytics/ga/overview` | POST | GA4 overview metrics |
| `/webhooks/analytics/ga/pages` | POST | Top pages |
| `/webhooks/analytics/ga/sources` | POST | Traffic sources |
| `/webhooks/analytics/ga/channels` | POST | Channel breakdown |
| `/webhooks/analytics/gsc/queries` | POST | Search queries |
| `/webhooks/analytics/gsc/opportunities` | POST | SEO opportunities |
| `/webhooks/analytics/db/leads` | POST | Database leads |
| `/webhooks/analytics/db/calls` | POST | Database calls |
| `/webhooks/analytics/db/funnel` | POST | Conversion funnel |
| `/webhooks/analytics/report/{type}` | POST | Generate report |

### TikTok

| Endpoint | Method | Mode | Description |
|----------|--------|------|-------------|
| `/webhooks/tiktok/stats` | POST | Sync | Account statistics |
| `/webhooks/tiktok/videos` | POST | Sync | Recent videos |
| `/webhooks/tiktok/winners` | POST | Sync | Winner videos |
| `/webhooks/tiktok/clients` | GET | Sync | List clients |
| `/webhooks/tiktok/scrape` | POST | Async | Scrape accounts |
| `/webhooks/tiktok/detect-winners` | POST | Async | Detect viral videos |
| `/webhooks/tiktok/generate` | POST | Async | Generate posts |
| `/webhooks/tiktok/metrics` | POST | Async | Update metrics |

### Cold Email

| Endpoint | Method | Mode | Description |
|----------|--------|------|-------------|
| `/webhooks/cold-email/warmup/status` | POST | Sync | Warmup status |
| `/webhooks/cold-email/warmup/ready` | POST | Sync | Ready accounts |
| `/webhooks/cold-email/accounts` | POST | Sync | List accounts |
| `/webhooks/cold-email/campaigns` | POST | Sync | List campaigns |
| `/webhooks/cold-email/dashboard` | POST | Sync | Dashboard |
| `/webhooks/cold-email/domain/check` | POST | Sync | Check domain |
| `/webhooks/cold-email/spam-check` | POST | Sync | Spam check |
| `/webhooks/cold-email/onboard` | POST | Async | Onboard domain |
| `/webhooks/cold-email/dns/setup` | POST | Async | Setup DNS |

### Tasks

| Endpoint | Method | Mode | Description |
|----------|--------|------|-------------|
| `/webhooks/tasks/extract` | POST | Async | Extract tasks from text |
| `/webhooks/tasks/deduplicate` | POST | Sync | Deduplicate tasks |

### Demo

| Endpoint | Method | Mode | Description |
|----------|--------|------|-------------|
| `/demo/job` | POST | Async | Submit the sample "summarize a topic" job |
| `/static/dashboard.html` | GET | — | Jobs dashboard (HTML/JS, served if `static/` present) |

### Jobs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/jobs` | GET | List all jobs |
| `/jobs/{job_id}` | GET | Get job details |
| `/jobs/{job_id}/status` | GET | Quick status check |
| `/jobs/{job_id}` | DELETE | Delete completed job |

### Clients

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/clients` | GET | List all clients |
| `/clients/{client_id}` | GET | Get client details |
| `/clients/{client_id}/analytics-config` | GET | Get analytics config |

## Request Format

All POST endpoints accept:

```json
{
  "client": "clawdbot",
  "options": {
    "limit": 30,
    "days": 7
  }
}
```

## Authentication

Include API key in header:

```bash
curl -X POST http://localhost:8088/webhooks/analytics/summary \
  -H "X-API-Key: $CMO_GATEWAY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"client": "clawdbot"}'
```

## Async Jobs

For long-running operations:

```bash
# Start job
curl -X POST http://localhost:8088/webhooks/tiktok/scrape \
  -H "X-API-Key: $KEY" \
  -d '{"client": "mdi"}'
# Returns: {"job_id": "abc123", "status": "pending"}

# Check status
curl http://localhost:8088/jobs/abc123 -H "X-API-Key: $KEY"
# Returns full job details with result when complete
```

## Production Deployment

1. **Install systemd service:**
   ```bash
   sudo cp gateway/cmo-gateway.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now cmo-gateway
   ```

2. **Check status:**
   ```bash
   sudo systemctl status cmo-gateway
   sudo journalctl -u cmo-gateway -f
   ```

3. **Optional: Nginx proxy:**
   ```nginx
   location /api/cmo/ {
       proxy_pass http://127.0.0.1:8088/;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
   }
   ```

## Usage Examples

### Cron job for daily analytics
```bash
# /etc/cron.d/cmo-analytics
0 8 * * * curl -X POST https://server/api/cmo/webhooks/analytics/summary \
  -H "X-API-Key: $KEY" -d '{"client": "clawdbot"}' >> /var/log/cmo-daily.log
```

### Slack slash command
```
/cmo analytics clawdbot
→ Triggers webhook → Returns summary in channel
```

### n8n/Zapier integration
```
Trigger: New email to cmo@domain.com
Action: POST to /webhooks/tasks/extract with parsed text
```

## Architecture

```
Trigger Sources (Slack/Cron/HTTP)
            │
            ▼
┌─────────────────────────────────┐
│    FastAPI Gateway (port 8088)  │
│  ┌───────────────────────────┐  │
│  │ Auth: API Key / Slack Sig │  │
│  └───────────────────────────┘  │
│  /webhooks/analytics/*          │
│  /webhooks/tiktok/*             │
│  /webhooks/cold-email/*         │
│  /webhooks/tasks/*              │
│  /jobs/{job_id}                 │
└─────────────────────────────────┘
            │
    ┌───────┴───────┐
    │               │
    ▼               ▼
 Sync           Async Jobs
(<10s)          (SQLite queue)
    │               │
    └───────┬───────┘
            ▼
   Python CLI Modules
   (scripts/analytics/, scripts/tiktok/, etc.)
```

## File Structure

```
gateway/
├── __init__.py
├── main.py              # FastAPI app, startup, routes
├── config.py            # Load clients_config.json + .env
├── auth.py              # API key middleware
├── jobs.py              # SQLite job queue + ThreadPoolExecutor
├── models.py            # Pydantic request/response schemas
├── requirements.txt     # FastAPI dependencies
├── README.md            # This file
├── cmo-gateway.service  # systemd service template
├── routers/
│   ├── analytics.py     # /webhooks/analytics/*
│   ├── tiktok.py        # /webhooks/tiktok/*
│   ├── cold_email.py    # /webhooks/cold-email/*
│   ├── tasks.py         # /webhooks/tasks/*
│   ├── clients.py       # /clients/*
│   └── jobs.py          # /jobs/*
└── adapters/
    ├── analytics_adapter.py   # Wrap scripts/analytics/
    ├── tiktok_adapter.py      # Wrap scripts/tiktok/
    ├── cold_email_adapter.py  # Wrap scripts/cold_email/
    └── tasks_adapter.py       # Wrap task scripts
```
