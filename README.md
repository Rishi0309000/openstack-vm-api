# OpenStack VM Lifecycle Management API

A production-ready REST API for managing OpenStack Virtual Machine lifecycle operations, built with **FastAPI** and **Python 3.10+**.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [API Design](#api-design)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Endpoints Reference](#endpoints-reference)
- [Running Tests](#running-tests)
- [Docker](#docker)
- [Design Decisions](#design-decisions)
- [Roadmap / Backlog](#roadmap--backlog)

---

## Overview

This project implements a REST API layer over OpenStack Nova (Compute) and Glance (Images) to provide clean, consistent VM lifecycle management. It supports two operating modes:

| Mode | Description |
|------|-------------|
| **Mock** (`MOCK_MODE=true`) | In-memory fake data — no real OpenStack required. Perfect for local dev and demos. |
| **Real** (`MOCK_MODE=false`) | Connects to a live OpenStack deployment via `keystoneauth1` + `python-novaclient`. |

The mock mode simulates realistic async state transitions (e.g., `BUILD → ACTIVE`) so you can exercise the full API without infrastructure.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Client / Consumer                     │
└────────────────────────────┬────────────────────────────────┘
                             │  HTTP / REST
┌────────────────────────────▼────────────────────────────────┐
│                    FastAPI Application                       │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  /api/v1/vms │  │  /api/v1/    │  │  /api/v1/images  │  │
│  │  (vms.py)    │  │  flavors     │  │  (images.py)     │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                 │                    │            │
│  ┌──────▼─────────────────▼────────────────────▼─────────┐  │
│  │              OpenStackClient (service layer)           │  │
│  │                                                        │  │
│  │  ┌─────────────────────┐  ┌──────────────────────┐    │  │
│  │  │   Mock Mode         │  │   Real Mode           │    │  │
│  │  │  (in-memory dict)   │  │  keystoneauth1        │    │  │
│  │  │  + async simulation │  │  + python-novaclient  │    │  │
│  │  └─────────────────────┘  └──────────────────────┘    │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                             │
                             │  (real mode only)
┌────────────────────────────▼────────────────────────────────┐
│                    OpenStack Cluster                         │
│   Keystone (Auth)  ·  Nova (Compute)  ·  Glance (Images)   │
└─────────────────────────────────────────────────────────────┘
```

### Project Structure

```
openstack-vm-api/
├── app/
│   ├── main.py                  # FastAPI app, middleware, routers
│   ├── api/
│   │   └── v1/
│   │       ├── vms.py           # VM lifecycle endpoints
│   │       ├── flavors.py       # Flavor endpoints
│   │       └── images.py        # Image endpoints
│   ├── core/
│   │   ├── config.py            # Pydantic Settings (env-driven)
│   │   └── exceptions.py        # Custom exception hierarchy
│   ├── schemas/
│   │   └── vm.py                # Request/Response Pydantic models
│   └── services/
│       └── openstack_client.py  # OpenStack abstraction + mock engine
├── tests/
│   └── unit/
│       └── test_api.py          # 25+ pytest-asyncio tests
├── .github/
│   └── workflows/
│       └── ci.yml               # GitHub Actions CI (lint + test + Docker)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
└── .env.example
```

---

## API Design

### Principles

- **REST-ful resource modelling**: VMs, Flavors, and Images are independent resources with standard CRUD patterns.
- **Action sub-resources**: Lifecycle operations (`/start`, `/stop`, `/reboot`, `/resize`) are expressed as POST to sub-resources rather than PATCH with a `status` field — this avoids ambiguity and aligns with OpenStack's own API convention.
- **Versioned prefix**: All endpoints live under `/api/v1/` to allow non-breaking evolution.
- **Consistent error envelope**: All errors return `{ "error": "ERROR_CODE", "message": "...", "request_id": "..." }`.
- **Request ID tracing**: Every response includes `X-Request-ID` and `X-Process-Time` headers for observability.
- **Pagination**: List endpoints support `page` + `page_size` query params with a `has_next` flag in the response.

### VM Lifecycle State Machine

```
          ┌─────────┐
    POST / │  BUILD  │
    create └────┬────┘
                │ (provisioning complete)
                ▼
          ┌─────────┐  POST /stop   ┌─────────┐
          │ ACTIVE  │ ────────────► │ SHUTOFF │
          │         │ ◄──────────── │         │
          └────┬────┘  POST /start  └─────────┘
               │
       POST /reboot ──► REBOOT / HARD_REBOOT ──► ACTIVE
               │
       POST /resize ──► RESIZE ──► VERIFY_RESIZE
                                        │
                             POST /confirm-resize
                                        │
                                     ACTIVE
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success (GET, POST action) |
| `201` | VM created |
| `204` | VM deleted (no body) |
| `400` | Bad request / validation error |
| `401` | Authentication required |
| `403` | Quota exceeded |
| `404` | Resource not found |
| `409` | Conflict (invalid state transition) |
| `422` | Unprocessable entity (schema validation) |
| `503` | OpenStack unreachable |

---

## Quick Start

### Prerequisites

- Python 3.10+
- pip

### 1. Clone and set up

```bash
git clone https://github.com/YOUR_USERNAME/openstack-vm-api.git
cd openstack-vm-api

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# MOCK_MODE=true is the default — no OpenStack needed
```

### 3. Run

```bash
uvicorn app.main:app --reload
```

The API is now live at **http://localhost:8000**

| URL | Purpose |
|-----|---------|
| http://localhost:8000/docs | Interactive Swagger UI |
| http://localhost:8000/redoc | ReDoc documentation |
| http://localhost:8000/health | Health check |

### 4. Try it out

```bash
# List flavors
curl http://localhost:8000/api/v1/flavors

# Create a VM
curl -X POST http://localhost:8000/api/v1/vms \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-vm",
    "flavor_id": "m1.small",
    "image_id": "img-ubuntu-22",
    "network_ids": ["private-net"]
  }'

# List VMs
curl http://localhost:8000/api/v1/vms

# Stop a VM (replace VM_ID)
curl -X POST http://localhost:8000/api/v1/vms/VM_ID/stop

# Delete a VM
curl -X DELETE http://localhost:8000/api/v1/vms/VM_ID
```

---

## Configuration

All configuration is via environment variables (or `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `MOCK_MODE` | `true` | Use in-memory mock instead of real OpenStack |
| `OS_AUTH_URL` | `http://localhost:5000/v3` | Keystone endpoint |
| `OS_USERNAME` | `admin` | OpenStack username |
| `OS_PASSWORD` | `secret` | OpenStack password |
| `OS_PROJECT_NAME` | `admin` | OpenStack project |
| `OS_USER_DOMAIN_NAME` | `Default` | User domain |
| `OS_PROJECT_DOMAIN_NAME` | `Default` | Project domain |
| `OS_REGION_NAME` | `RegionOne` | OpenStack region |
| `OS_COMPUTE_API_VERSION` | `2.87` | Nova microversion |
| `OS_CONNECT_TIMEOUT` | `10` | Connection timeout (seconds) |
| `OS_READ_TIMEOUT` | `30` | Read timeout (seconds) |
| `DEFAULT_PAGE_SIZE` | `20` | Default pagination size |
| `MAX_PAGE_SIZE` | `100` | Max pagination size |

---

## Endpoints Reference

### VMs — `/api/v1/vms`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/vms` | List VMs (filterable, paginated) |
| `POST` | `/api/v1/vms` | Create a VM |
| `GET` | `/api/v1/vms/{id}` | Get VM details |
| `DELETE` | `/api/v1/vms/{id}` | Delete a VM |
| `POST` | `/api/v1/vms/{id}/start` | Start a stopped VM |
| `POST` | `/api/v1/vms/{id}/stop` | Stop a running VM |
| `POST` | `/api/v1/vms/{id}/reboot` | Reboot (SOFT or HARD) |
| `POST` | `/api/v1/vms/{id}/resize` | Resize to a new flavor |
| `POST` | `/api/v1/vms/{id}/confirm-resize` | Confirm a pending resize |
| `PATCH` | `/api/v1/vms/{id}/metadata` | Update metadata |

#### List VMs Query Params

| Param | Type | Description |
|-------|------|-------------|
| `status` | string | Filter by status (e.g. `ACTIVE`, `SHUTOFF`) |
| `search` | string | Filter by name substring |
| `page` | int | Page number (default: 1) |
| `page_size` | int | Items per page (default: 20, max: 100) |

### Flavors — `/api/v1/flavors`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/flavors` | List all flavors |
| `GET` | `/api/v1/flavors/{id}` | Get flavor details |

### Images — `/api/v1/images`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/images` | List all images |
| `GET` | `/api/v1/images/{id}` | Get image details |

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | API liveness check |
| `GET` | `/health/openstack` | OpenStack connectivity check |

---

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# With coverage report
pytest tests/ -v --cov=app --cov-report=term-missing

# Run a specific test
pytest tests/unit/test_api.py::test_create_vm -v
```

The test suite covers:
- Health endpoints
- Flavor and Image CRUD
- VM creation, retrieval, deletion
- All lifecycle actions (start, stop, reboot, resize, confirm-resize)
- Metadata updates
- State transition validation (409 on invalid transitions)
- Input validation (422 on bad payloads)
- Pagination
- Request ID / timing headers

---

## Docker

### Build and run

```bash
docker build -t openstack-vm-api .
docker run -p 8000:8000 -e MOCK_MODE=true openstack-vm-api
```

### Docker Compose

```bash
docker compose up
```

---

## Design Decisions

### FastAPI over Flask / Django REST Framework

FastAPI was chosen for:
- **Native async** support — essential for I/O-bound OpenStack API calls
- **Auto-generated OpenAPI docs** from type annotations (zero extra work)
- **Pydantic v2** for validation with clear, descriptive error messages
- **Performance** — comparable to Node.js/Go for I/O workloads

### Service Layer Pattern

`OpenStackClient` in `app/services/openstack_client.py` encapsulates all OpenStack interactions. Routers call only the service — they have no knowledge of Nova, Keystone, or mock data. This makes:
- Swapping backends trivial (mock ↔ real, or Nova ↔ alternative)
- Unit testing fast and dependency-free
- Adding caching, retry logic, or circuit-breaking non-invasive

### Mock Mode with Async State Simulation

Rather than requiring a full DevStack/Packstack setup for local dev, `MOCK_MODE=true` provides:
- Realistic in-memory VM store
- `asyncio.create_task()` background tasks that simulate `BUILD → ACTIVE` and `RESIZE → VERIFY_RESIZE` transitions
- Full error path coverage (404, 409 state guards, quota limits)

### Pydantic Settings for Config

All configuration is driven by environment variables via `pydantic-settings`. This follows [12-Factor App](https://12factor.net/config) principles and makes the service trivially configurable in Kubernetes, Docker, or bare-metal without code changes.

### Exception Hierarchy

A typed exception hierarchy (`OpenStackAPIError` base + domain-specific subclasses) with a global FastAPI exception handler produces a consistent error envelope across all failure modes, avoiding ad-hoc `HTTPException` scattered across route handlers.

### API Versioning

The `/api/v1/` prefix allows future breaking changes to be introduced as `/api/v2/` while keeping existing consumers unaffected.

### Action Sub-Resources vs. PATCH status

`POST /vms/{id}/stop` is used instead of `PATCH /vms/{id} { "status": "SHUTOFF" }` because:
- Actions are imperative commands, not state declarations
- Each action can have its own request body (e.g., `reboot_type`)
- Aligns with OpenStack's own API design and REST best practices for operations that trigger async processes

---

## Roadmap / Backlog

Items beyond the assessment time-box, prioritised for a real production service:

### P0 – Security & Auth
- [ ] **Token authentication middleware** — validate `X-Auth-Token` against Keystone on every request
- [ ] **RBAC** — role-based access (admin vs. user vs. read-only)
- [ ] **Rate limiting** — per-tenant request throttling (e.g., via `slowapi`)
- [ ] **TLS termination** — enforce HTTPS in production

### P1 – Reliability
- [ ] **Retry with exponential backoff** on transient OpenStack errors
- [ ] **Circuit breaker** — fail fast when OpenStack is degraded
- [ ] **Async polling / webhooks** — notify clients when long-running operations (resize, build) complete
- [ ] **Distributed tracing** — OpenTelemetry integration for end-to-end request tracing

### P2 – Operations
- [ ] **Prometheus metrics** — `/metrics` endpoint (request latency, error rate, VM counts)
- [ ] **Structured JSON logging** — with correlation IDs, tenant context
- [ ] **Kubernetes manifests** — Deployment, Service, HPA, ConfigMap, Secret templates
- [ ] **Helm chart** — parameterised release management

### P3 – Feature Completeness
- [ ] **Console / VNC access** — proxy console URLs
- [ ] **Snapshots / backup** — image creation from running VMs
- [ ] **Floating IPs** — associate/disassociate public IPs
- [ ] **Volume management** — attach/detach Cinder block volumes
- [ ] **Keypair management** — CRUD for SSH keypairs
- [ ] **Security group management** — full lifecycle
- [ ] **Bulk operations** — start/stop multiple VMs in one call
- [ ] **Server groups** — affinity/anti-affinity scheduling hints
- [ ] **Live migration** — move VMs between compute hosts

### P4 – Developer Experience
- [ ] **Integration test suite** — against a real DevStack or MicroStack deployment in CI
- [ ] **OpenAPI client generation** — publish typed SDKs (Python, TypeScript)
- [ ] **Pre-commit hooks** — black + ruff + mypy on every commit
- [ ] **API changelog** — CHANGELOG.md with semantic versioning

---

## License

MIT

---

## Why We Built It This Way

This section explains every major decision made during development — the thinking behind the technology choices, architecture, and implementation approach.

### Why FastAPI over Flask or Django?

Flask and Django are great frameworks but they were not the right fit here. OpenStack API calls are network I/O bound — they involve HTTP requests to Keystone, Nova, and Glance that can take hundreds of milliseconds. FastAPI is built on async Python from the ground up, which means it can handle many concurrent OpenStack requests without blocking. Flask is synchronous by default and would need extra libraries (like gevent) to achieve the same concurrency. Django brings too much overhead for a pure API service.

FastAPI also auto-generates interactive Swagger documentation from the code itself — zero extra work. For an API assessment this is extremely valuable because reviewers can test every endpoint directly in the browser without writing a single line of code.

### Why Pydantic for validation?

Every incoming request is validated automatically against a strict schema before it even reaches our business logic. If someone sends a VM creation request without a name, or with an empty network list, Pydantic catches it and returns a clear 422 error with exactly which field failed and why. Without Pydantic we would have to write defensive checks manually throughout the codebase. Pydantic v2 also generates the OpenAPI schema automatically, which powers the Swagger UI.

### Why a Service Layer pattern?

The `OpenStackClient` class in `app/services/openstack_client.py` is the only place in the entire codebase that knows about OpenStack. The API routers (vms.py, flavors.py, images.py) only call the service — they have no idea whether the data is coming from a real OpenStack cluster or from the in-memory mock.

This matters for three reasons:
1. **Testability** — tests run in milliseconds without needing real infrastructure
2. **Replaceability** — switching from Nova to a different backend only requires changing the service, not the API layer
3. **Maintainability** — OpenStack connection logic, retries, and error handling are in one place

### Why Mock Mode?

A real OpenStack deployment requires DevStack or Packstack, which takes 30-60 minutes to set up and significant compute resources. For a proof-of-concept and assessment, requiring reviewers to set up OpenStack just to run the code would be a barrier. Mock mode provides:

- Realistic in-memory VM storage
- Simulated state transitions (BUILD → ACTIVE happens automatically after 2 seconds using `asyncio.create_task`)
- Full error path coverage (404 when VM not found, 409 when wrong state)
- Quota simulation (max 20 VMs)

Setting `MOCK_MODE=false` and providing real OpenStack credentials switches to the live implementation instantly.

### Why these specific REST conventions?

**Action sub-resources** (`POST /vms/{id}/stop`) instead of `PATCH /vms/{id} {"status": "SHUTOFF"}`:
- Actions are commands, not state declarations
- Each action can have its own request body (e.g. reboot needs `reboot_type`)
- This matches OpenStack's own API design philosophy
- Clearer intent — "stop this VM" vs "set status to SHUTOFF"

**Versioned prefix** (`/api/v1/`):
- Allows future breaking changes as `/api/v2/` without affecting existing consumers
- Industry standard for production APIs

**Consistent error envelope**:
```json
{"error": "VM_NOT_FOUND", "message": "VM 'abc' not found", "request_id": "..."}
```
Every error across every endpoint returns the same structure. Consumers can write one error handler for all cases.

### Why Request ID and timing headers?

Every response includes `X-Request-ID` and `X-Process-Time` headers. In production systems these are essential for debugging — when a user reports an issue, you can search logs by request ID and find exactly what happened. Process time lets you identify slow endpoints. These are free to add as middleware and provide significant operational value.

### Why pytest-asyncio for testing?

The entire API is async. Standard pytest cannot run async test functions. pytest-asyncio allows writing async test functions naturally and integrates with FastAPI's test client via httpx's `AsyncClient`. All 26 tests run in under 2 seconds with no real infrastructure needed.

### Why Docker?

Docker ensures the API runs identically on any machine — the reviewer's laptop, a CI server, or a production Kubernetes cluster. The Dockerfile uses a non-root user for security, multi-stage dependency caching for fast builds, and a health check so orchestrators know when the service is ready.

### Why GitHub Actions CI?

Every push automatically runs:
1. Lint check (ruff) — catches code quality issues
2. Tests on Python 3.11 and 3.12 — ensures compatibility
3. Docker build + smoke test — ensures the container actually starts

This means the reviewer can see green checkmarks on the repository and know the code is verified, not just "works on my machine".

### What would be next in production?

The roadmap section covers this in detail, but the highest priority items would be:
- **Authentication** — validate OpenStack tokens on every request via Keystone middleware
- **Rate limiting** — prevent abuse per tenant
- **Circuit breaker** — fail fast when OpenStack is degraded rather than hanging
- **Prometheus metrics** — track request latency and error rates
- **Structured logging** — JSON logs with correlation IDs for production debugging