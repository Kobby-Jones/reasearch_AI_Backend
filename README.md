# ResearchAI Backend (RAI-Core)

A production-oriented, modular FastAPI backend powering an AI-assisted academic
research platform. It helps students generate research topics, design and
validate questionnaires, upload datasets, run **deterministic** statistical
analysis, get AI interpretations, simulate a viva defense, generate thesis
chapters, and manage subscriptions + payments.

> **Core principle:** the AI **never** performs calculations. Every statistic is
> computed by `pandas` / `numpy` / `scipy` / `statsmodels` in `app/analytics`.
> The language model only reasons and writes prose.

---

## Architecture (strict layered separation)

```
HTTP  ─▶  API layer (app/api)            # request/response only, no logic
          Service layer (app/services)   # business logic + ALL feature gating
          ├─ AI layer (app/ai)           # provider-switchable LLM orchestration
          ├─ Analytics engine (app/analytics)  # deterministic statistics
          ├─ Document generator (app/utils/document_generator.py)
          └─ Repository layer (app/repositories)  # DB access only
                    │
                Models (app/models)  ─▶  PostgreSQL (SQLite fallback in dev)
```

| Layer | Responsibility |
|-------|----------------|
| API | HTTP routing, validation via Pydantic schemas, auth dependency |
| Service | Business rules, feature gating, usage tracking, orchestration |
| AI | `AIClient` abstraction over OpenAI / Claude / mock |
| Analytics | Pure-Python statistics (descriptive, correlation, regression, ANOVA, frequency) |
| Document | DOCX / PDF report rendering |
| Repository | SQLAlchemy queries only |

---

## Tech stack

Python 3.11+ · FastAPI · Pydantic v2 · SQLAlchemy 2.0 · PostgreSQL · Alembic ·
Pandas · NumPy · SciPy · Statsmodels · Uvicorn · httpx ·
python-docx + reportlab. Optional: Redis, Celery.

AI providers (switchable via `AI_PROVIDER`): **mock** (default, zero-config),
**openai**, **claude**.

Payments: **Paystack** (primary), Flutterwave (optional fallback hook).

---

## Quick start

```bash
# 1. install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. configure (optional — sensible dev defaults are built in)
cp .env.example .env
#   By default AI_PROVIDER=mock and DATABASE_URL is blank → SQLite file.
#   The whole system runs end-to-end with NO external keys.

# 3. run
uvicorn app.main:app --reload
```

Open the interactive docs at <http://localhost:8000/docs>.

### Switching to real infrastructure
- **PostgreSQL**: set `DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/db`.
- **Migrations**: a baseline migration is included. Set `AUTO_CREATE_TABLES=false`
  and run `alembic upgrade head` to create the schema. Generate new revisions
  with `alembic revision --autogenerate -m "<change>"` as the models evolve.
- **Real AI**: set `AI_PROVIDER=openai` (+`OPENAI_API_KEY`) or `claude` (+`ANTHROPIC_API_KEY`).
- **Payments**: set `PAYSTACK_SECRET_KEY` to enable live initialise/verify/webhook.
  Point your Paystack webhook at `POST {API_PREFIX}/payment/webhook`.

### Production checklist (enforced at startup)
When `ENVIRONMENT=production`, the app **refuses to boot** unless all of the
following are satisfied — so a misconfiguration fails loudly instead of running
insecurely:

- `SECRET_KEY` is a unique random value ≥ 32 chars
  (`python -c "import secrets; print(secrets.token_urlsafe(48))"`).
- `DEBUG=false` and `AUTO_CREATE_TABLES=false` (schema via `alembic upgrade head`).
- `DATABASE_URL` points at PostgreSQL.
- `CORS_ORIGINS` is an explicit comma-separated allowlist (not `*`).
- `PAYSTACK_SECRET_KEY` is set (webhook signatures and transactions are verified;
  unsigned/invalid webhooks are rejected, and the charged amount/currency is
  checked before a plan is unlocked).
- The matching AI key is set for the selected `AI_PROVIDER`.

---

## Subscription tiers & feature gating

All gating is enforced in the **service layer** via `app/services/feature_gate.py`.

| Feature | FREE | BASIC | PREMIUM |
|--------|------|-------|---------|
| Questionnaire generation | 3 / month | Unlimited | Unlimited |
| Analysis runs | 5 / month | Unlimited | Unlimited |
| Report export (PDF/DOCX) | Watermarked | ✅ | ✅ |
| Standard AI interpretation | ✅ | ✅ | ✅ |
| Advanced AI interpretation | ❌ | ❌ | ✅ |
| Viva simulation | ❌ | ❌ | ✅ |

Usage (AI calls, analysis runs, questionnaire generations, report exports) is
tracked per user per month in the `usage_records` table for scaling and pricing.

### Payment flow
1. `POST /payment/initiate` → backend creates a pending `payments` row and (if a
   Paystack key is set) returns an `authorization_url`.
2. User pays externally.
3. Paystack calls `POST /payment/webhook` (HMAC-SHA512 signature verified).
4. On `charge.success` the subscription is **activated automatically**.
   `GET /payment/verify/{reference}` offers a server-to-server fallback.

---

## API endpoints (prefix `/api/v1`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Create account (starts on FREE) |
| POST | `/auth/login` | Get a JWT bearer token |
| POST | `/research/topic` | Break a topic into variables/objectives/hypotheses |
| GET | `/research` | List the current user's projects (newest first) |
| GET | `/research/{id}` | Fetch a project |
| POST | `/questionnaire/generate` | Generate a structured questionnaire |
| GET | `/questionnaire?project_id=` | List questionnaires for an owned project |
| POST | `/questionnaire/validate` | Validate a questionnaire structure |
| POST | `/dataset/upload` | Upload CSV/Excel (schema detect + clean) |
| GET | `/dataset?project_id=` | List datasets for an owned project |
| POST | `/analysis/run` | Run a deterministic statistical analysis |
| GET | `/analysis?dataset_id=` or `?project_id=` | List analyses (one filter required) |
| POST | `/analysis/interpret` | AI interpretation of computed results |
| POST | `/viva/start` | Start a viva session (PREMIUM) |
| GET | `/viva?project_id=` | List viva sessions for an owned project |
| POST | `/viva/respond` | Answer + get scored (PREMIUM) |
| POST | `/report/generate` | Generate a DOCX/PDF thesis report |
| POST | `/payment/initiate` | Initialise a payment |
| GET | `/payment` | List the current user's payment history |
| POST | `/payment/webhook` | Paystack webhook |
| GET | `/subscription/status` | Plan, usage and limits |

All `GET` list endpoints are ownership-scoped (a user only ever sees their own
data; requesting another user's project returns `404`) and accept optional
`limit` (1–200, default 100) and `offset` (default 0) query parameters for
pagination. Results are ordered newest-first.

### Datasets / SPSS
Upload `.csv` or `.xlsx`/`.xls`. For SPSS, export to CSV (`File ▸ Save As ▸ CSV`)
or Excel first, then upload.

---

## Example API calls

```bash
BASE=http://localhost:8000/api/v1

# Register + login
curl -s -X POST $BASE/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"ama@example.com","password":"supersecret","full_name":"Ama"}'

TOKEN=$(curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"ama@example.com","password":"supersecret"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Create a research project from a topic
curl -s -X POST $BASE/research/topic -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"topic":"Effect of mobile learning on student performance","field":"Education"}'

# Generate a questionnaire for project 1
curl -s -X POST $BASE/questionnaire/generate -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"project_id":1,"items_per_section":5}'

# Upload a dataset (multipart)
curl -s -X POST $BASE/dataset/upload -H "Authorization: Bearer $TOKEN" \
  -F project_id=1 -F file=@data.csv

# Run a regression
curl -s -X POST $BASE/analysis/run -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"dataset_id":1,"analysis_type":"regression","dependent":"score","independents":["hours","age"]}'

# Interpret it
curl -s -X POST $BASE/analysis/interpret -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"analysis_id":1,"style":"standard"}'

# Subscription status
curl -s $BASE/subscription/status -H "Authorization: Bearer $TOKEN"

# Initiate an upgrade to premium
curl -s -X POST $BASE/payment/initiate -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"plan":"premium"}'
```

---

## Project structure

```
rai_backend/
├── app/
│   ├── main.py                 # FastAPI app
│   ├── core/                   # config, db, security, deps, exceptions
│   ├── api/                    # routers (HTTP only)
│   ├── services/               # business logic + feature gating
│   ├── ai/                     # AIClient + providers (openai/claude/mock)
│   ├── analytics/              # deterministic statistics engine
│   ├── models/                 # SQLAlchemy models
│   ├── schemas/                # Pydantic v2 schemas
│   ├── repositories/           # DB access
│   └── utils/                  # dataset loader, usage tracker, doc generator
├── migrations/                 # Alembic
├── alembic.ini
├── requirements.txt
├── .env.example
└── README.md
```

## Notes
- Default dev DB is SQLite for zero-config startup; PostgreSQL is the production target.
- `AUTO_CREATE_TABLES=true` creates tables on startup in dev; disable and use
  Alembic in production.
- The `mock` AI provider returns deterministic, clearly-labelled placeholders so
  every endpoint is exercisable without API keys.
