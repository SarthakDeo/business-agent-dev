# Gnani AI Business Agent

> Prisma hears. Evon thinks. Your agent decides. n8n acts. PostgreSQL remembers.

## Quick Start

### Prerequisites
- Docker Desktop (installed ✅)
- Node.js 24+ (installed ✅)
- Git (installed ✅)
- Python 3.11+ (install if needed)

### 1. Clone & Setup
```bash
cd c:\Users\Lenovo\Desktop\GnaniAI\project

# Copy environment file and fill in your credentials
copy .env.example .env
# Edit .env with your actual Gnani API key, Gmail, Slack credentials
```

### 2. Start Infrastructure (Docker)
```bash
cd docker
docker-compose up -d
```

This starts:
- **PostgreSQL** on port `5432` — auto-creates schema + demo data
- **n8n** on port `5678` — workflow execution engine
- **Redis** on port `6379` — caching layer

### 3. Verify Everything is Running
```bash
docker-compose ps
# All 3 services should show "Up"

# Test PostgreSQL
docker exec gnani_postgres psql -U gnani -d gnani_agent -c "\dt"

# Open n8n in browser
# http://localhost:5678
# Login: admin / gnani_n8n_secret
```

## Project Structure
```
project/
├── frontend/nextjs-app/        ← Next.js UI
├── backend/
│   ├── api/                    ← FastAPI endpoints
│   └── agent/                  ← Core agent modules
│       ├── planner.py
│       ├── tool_selector.py
│       ├── tool_registry.py
│       ├── context_manager.py
│       ├── permission_manager.py
│       ├── validator.py
│       ├── confirmation_manager.py
│       ├── execution_manager.py
│       └── response_generator.py
├── gnani/
│   ├── prisma/                 ← Speech-to-text client
│   └── evon/                   ← LLM reasoning client
├── n8n/workflows/              ← n8n workflow definitions
├── database/
│   ├── schema.sql              ← 16-table PostgreSQL schema
│   └── seed.sql                ← Demo org + fake data
├── docker/
│   └── docker-compose.yml      ← PostgreSQL + n8n + Redis
├── docs/
│   ├── tool_registry.yaml      ← 10 canonical tool definitions
│   └── agent_json_schema.json  ← Evon output schema contract
└── .env.example                ← Environment variable template
```

## Architecture
```
Voice/Text → Gnani Prisma → FastAPI → Agent Service → Gnani Evon
                                            ↓
                                      Tool Registry
                                            ↓
                                           n8n
                                    ↙    ↓    ↘
                                Gmail   CRM   Slack
                                            ↓
                                       PostgreSQL
```

## Build Phases
- [ ] Phase 1: Test Gnani Prisma + Evon APIs independently
- [ ] Phase 2: Build Agent modules + Tool Registry
- [ ] Phase 3: n8n workflows for Gmail, CRM, Slack
- [ ] Phase 4: End-to-end dynamic execution
- [ ] Phase 5: ASK / DO / AUTOMATE modes
- [ ] Phase 6: Permissions, risk scoring, confirmations
- [ ] Phase 7: PostgreSQL memory + audit logs
- [ ] Phase 8: Next.js dashboard + chat/voice UI
- [ ] Phase 9: WhatsApp + Calendar
- [ ] Phase 10: Voice output with Gnani Timbre

