# IMAGIN Virtualization Platform — Project Context

## Overview

IMAGIN is a virtualization platform developed for a university environment. Its goal is to give students and researchers a simple, intuitive interface to deploy and manage virtual infrastructures for various use cases, including:

- **5G network infrastructures**
- **Federated learning experiments**
- **Cyberfield environments** for adversary simulation and security research

Infrastructures are deployed as Docker containers or Kubernetes clusters. The platform is designed to be operated as a SaaS: individual professors (or admins) can spin up their own instance and offer it to their students, each instance being fully self-contained.

---

## Architecture

The platform consists of three services, orchestrated via **Docker Compose** and running on a VPS:

```
┌────────────────────────────────────────────────────────┐
│                     Docker Compose                     │
│                                                        │
│  ┌──────────┐   ┌──────────┐   ┌────────────────────┐ │
│  │  Traefik │   │ Backend  │   │  Frontend (Godot)  │ │
│  │ (ingress)│──▶│ FastAPI  │   │  Served as web app │ │
│  │ :80/:443 │   │ :8000    │   │  :80               │ │
│  └──────────┘   └──────────┘   └────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

- **Traefik** acts as the reverse proxy / ingress controller. It routes `/api/*` to the backend and everything else to the frontend. It also dynamically generates routes for deployed cluster web UIs (e.g., Headlamp dashboards).
- **Backend** is a Python FastAPI application running on port 8000, with access to the Docker daemon and to the Traefik dynamic config directory.
- **Frontend** is a Godot 4.6 application exported as a web app (GL Compatibility renderer), served by a simple HTTP server.

Configuration is provided via a `.env` file at the project root (`DOMAIN_NAME`, `ENDPOINT_PATH_BASE`).

---

## Backend

**Language/Framework:** Python 3, FastAPI, Uvicorn
**Database:** DuckDB (file-based, `index.db`)
**Entry point:** `backend/main.py`

### Structure

```
backend/
├── main.py            # App entry, CORS, router registration, startup hook
├── db.py              # DuckDB helpers: execute(), fetch_all(), get_seq_current_val()
├── db_init.sql        # Database schema (see below)
├── requirements.txt
├── Dockerfile
├── api/               # FastAPI route modules
│   ├── _template.py   # Template for new route files — follow this pattern
│   ├── auth.py
│   ├── project.py
│   ├── infra.py
│   ├── registry.py
│   ├── storage.py
│   └── experiment.py
└── infra/             # Infrastructure operation modules
    ├── container.py   # Docker container operations
    ├── k8s.py         # Kubernetes cluster operations (via Python k8s client)
    ├── k3d.py         # K3D local cluster provisioning
    ├── traefik.py     # Traefik dynamic route generation
    └── flower.py      # Flower (federated learning monitoring)
```

### API Conventions

All routes are prefixed with `/api` by Traefik (stripped before reaching FastAPI). Each route module follows the pattern defined in `backend/api/_template.py`:

1. **SCHEMAS** — Pydantic `BaseModel` classes for request and response bodies
2. **ENDPOINTS** — FastAPI route handlers; always authenticate first with `auth.get_user_by_token(auth.get_token(authorization))`, then delegate to logic functions
3. **LOGIC** — Private functions (prefixed `_`) that contain the actual business logic and DB access

Authentication is token-based. Every protected endpoint takes `authorization: str = Header(None)` and calls `auth.get_user_by_token()` before doing anything.

### Database Schema

All tables use DuckDB sequences for primary keys. Key tables:

| Table | Purpose |
|---|---|
| `Roles` | System roles (`admin`, `user`) |
| `Users` | User accounts (username, email, hashed password, role) |
| `Sessions` | Auth tokens with expiry, IP, and user agent |
| `Projects` | Top-level project containers |
| `ProjectRoles` | Role definitions at the project level |
| `ProjectUsers` | Many-to-many: users ↔ projects, with a project role |
| `Infra` | Infrastructure records (type + JSON config, linked to project) |
| `Experiments` | Experiment records (type + JSON config, linked to project) |

`infra_config` and `experiment_config` are stored as JSON text in `TEXT` columns. When reading or writing these, always serialize/deserialize as JSON.

### Infrastructure Modules (`backend/infra/`)

Common infrastructure logic is extracted here by domain — **do not embed infrastructure operations directly in API route handlers**. The convention is:

- `container.py` → any Docker container operation
- `k8s.py` → any Kubernetes operation (uses the official Python `kubernetes` client)
- `k3d.py` → K3D cluster provisioning
- `traefik.py` → dynamic Traefik route generation (writes YAML to `TRAEFIK_DYNAMIC_DIR`)
- `flower.py` → Flower/federated learning monitoring

When adding support for a new infrastructure type or operation, create or extend the appropriate module in `backend/infra/` and call it from the API layer.

### Cluster Web UI Exposure

When a Kubernetes cluster has its web UI enabled (Headlamp), the backend:
1. Deploys Headlamp into the cluster via `k8s.py`
2. Generates a unique `endpoint_id`
3. Writes a Traefik dynamic route config via `traefik.py`, exposing the UI at `https://<DOMAIN_NAME><ENDPOINT_PATH_BASE>/<endpoint_id>/`

On startup, `main.py` calls `infra.reconcile_cluster_web_ui_endpoints()` to restore Traefik routes for all running clusters.

---

## Frontend (Godot)

**Engine:** Godot 4.6 (GL Compatibility renderer — required for web export)
**Export:** Web (HTML5), served as a static site
**Location:** `frontend/`

### Autoloads (Global Singletons)

Autoloads are globally accessible in any scene. All HTTP communication goes through the `Http` autoload.

| Autoload | File | Responsibility |
|---|---|---|
| `Config` | `autoloads/config.gd` | Persists `auth_token` and `language` to `user://config.cfg` |
| `Auth` | `autoloads/auth.gd` | Tracks logged-in user state; emits `logged_in` / `logged_out` signals |
| `Http` | `autoloads/http/http.gd` | Async HTTP requests; returns `HttpResponse` objects |
| `Context` | `autoloads/context.gd` | Holds current project and registries data for the active session |
| `Events` | `autoloads/events.gd` | App-wide signal/event bus |
| `Dialog` | `autoloads/dialog/dialog.tscn` | Global dialog management |

### HTTP Communication

All API calls go through `Http.send_request(url, headers, method, data, error_msg)`. Auth headers (Bearer token + JSON content type) are defined in `Auth` and passed to each request. The response is wrapped in an `HttpResponse` object.

### Page System

Navigation is built around a custom `Page` base class (`pages/page.gd`, extends `Control`). Each page:
- Has an exported `title` and optional `icon`
- Can navigate forward with `push_page(page_uid, args)` or back with `pop_back()`
- Pages are registered in `page_catalog.gd`

**Page hierarchy:**
```
auth/login_page         → Login screen
main/main               → App shell after login
  project_list/         → Lists all projects; create project dialog
  project_detail/       → Tabbed view for a single project
    infra/              → Infrastructure tab
    cluster/            → Kubernetes cluster tab
    experiments/        → Experiments tab
    registry/           → Container registry tab
    storage/            → Storage tab
```

### Reusable Components

Shared UI components live in `frontend/components/`:
- `buttons/` — styled button variants
- `breadcomb/` — breadcrumb navigation
- `loading/` — loading spinners
- `language/` — language selector (EN/FR)
- `managment/` — generic create/edit/delete dialogs

### Translations

The app supports **English and French**. Translation files are in `frontend/res/`. Always add new UI strings to both translation files.

---

## Deployment

### Development
- Backend: run `uvicorn main:app --reload` directly inside `backend/`
- Frontend: open in Godot Editor and run or export

### Production
```bash
cp .env.example .env
# Fill in DOMAIN_NAME and ENDPOINT_PATH_BASE
# Place TLS certs in traefik/certs/ (fullchain.pem, privkey.pem)
docker compose up -d
```

Traefik handles TLS termination. HTTP is automatically redirected to HTTPS.

---

## Key Development Guidelines

1. **API routes are thin.** All business and infrastructure logic goes in `backend/infra/` modules or dedicated helper files — not inline in route handlers.
2. **Follow the route template.** Every new API module should mirror the structure in `backend/api/_template.py`: SCHEMAS → ENDPOINTS → LOGIC.
3. **Authentication first.** Every protected route must call `auth.get_user_by_token()` before touching any data.
4. **Access control.** Use `project.user_has_project_access(user_id, project_id)` before any project-scoped operation.
5. **Infrastructure is modular.** New infrastructure types go in `backend/infra/` as their own module or an extension of an existing one.
6. **HTTP goes through `Http` autoload.** No direct `HTTPRequest` nodes in individual scenes; always use the singleton.
7. **State is in autoloads.** App-wide state (user, project, context) lives in autoloads, not in individual scene scripts.
8. **Translations.** All user-facing strings in Godot must be added to both EN and FR translation files.
9. **Database access via `db.py`.** Never use DuckDB directly in route handlers; use the helpers in `db.py`.
10. **`infra_config` and `experiment_config` are JSON strings.** Always parse/serialize them explicitly.
