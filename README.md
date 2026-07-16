# Property Management System — Phase 1: Project Foundation

Cloud-native PMS built for a company that leases properties from owners and
subleases them to tenants. This phase delivers the platform foundation:
authentication, RBAC, organization setup, and cross-cutting system
infrastructure (attachments, notes, activity log, audit log, notifications).

Stack: **FastAPI + PostgreSQL** (backend) · **React + TypeScript + Tailwind**
(frontend) · **Docker** · designed for **Azure** deployment.

## Quick Start (local, via Docker)

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker-compose up --build
```

This will:
1. Start PostgreSQL
2. Run Alembic migrations (`alembic upgrade head`)
3. Run `seed.py` (permissions, roles, admin user, lookup data)
4. Start the FastAPI backend on **http://localhost:8000**
5. Start the React frontend on **http://localhost:5173**

API docs (Swagger): **http://localhost:8000/api/v1/docs**

## Default login

| Role | Email | Password |
|---|---|---|
| Administrator | `admin@pms-demo.com` | `Admin@12345` |
| Branch Manager | `maria.manager@pms-demo.com` | `ChangeMe!123` |
| Staff | `sam.staff@pms-demo.com` | `ChangeMe!123` |

**Change these immediately after first login in any non-local environment.**

## Manual setup (without Docker)

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # then edit DATABASE_URL to point at your Postgres instance
alembic upgrade head
python seed.py
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

### Running tests
```bash
cd backend
pytest
```

## Project structure

```
pms/
├── backend/
│   ├── app/
│   │   ├── core/            # config, database, security
│   │   ├── models/          # SQLAlchemy models (all inherit BaseModel)
│   │   ├── schemas/         # Pydantic DTOs
│   │   ├── repositories/    # Repository pattern (data access)
│   │   ├── services/        # Business logic / service layer
│   │   ├── api/v1/routers/  # FastAPI route handlers
│   │   └── alembic/         # DB migrations
│   ├── tests/                # pytest suite
│   ├── seed.py                # seed data script
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/            # route-level pages
│   │   ├── components/       # reusable UI + layout
│   │   ├── context/          # Auth + Theme context
│   │   ├── api/               # axios client
│   │   └── types/             # shared TS types
│   └── Dockerfile
├── docker-compose.yml
└── docs/                      # testing, deployment, security checklists (this phase's deliverables)
```

See `/docs` for the full Phase 1 testing checklist, UAT script, permissions
matrix, and deployment guide. Phase 2 (Property Owners) adds
`docs/phase2-testing-checklist.md` and `docs/phase2-uat-script.md`.

## Phase 2: Property Owners

Adds the first business entity: Property Owners (individual or company),
each with addresses, bank accounts, additional contacts, and legal
documents (with expiry tracking) — plus search, filters, and a dedicated
owner dashboard. This is the first link in the business chain: **Owner →
Lease Agreement → Company → Sublease → Tenant** (later phases build the
rest of that chain on top of this).

New migration: `0002_property_owners.py`. New permission module: `owners`
(view/create/edit/delete). Run `python seed.py` again after migrating to
load 2 sample owners.
