# TechConf — Repository & Code Structure

> This file answers all the decision questions from §7 of the exam spec.
> Every task Kiro generates must be consistent with the decisions recorded here.

---

## Repository Layout

**Decision:** Single monorepo for all services.

**Why:** The acceptance suite (`tests/integration/`) lives at the repo root and expects all
services to be reachable via `services.yaml`. A monorepo keeps the suite runnable with a
single `pytest` command, simplifies environment setup, and makes it straightforward to add
the two optional services later. It does NOT mean services share runtime code — each
service is an isolated Python package with its own `requirements.txt`.

```
techconf-exam/                          ← repo root
│
├── contracts/                          ← DO NOT MODIFY
│   ├── openapi/                        ← DO NOT MODIFY
│   └── validator.py                    ← DO NOT MODIFY
│
├── tests/
│   └── integration/                    ← DO NOT MODIFY (acceptance suite)
│
├── services/                           ← all service implementations live here
│   ├── user-service/
│   ├── event-service/
│   ├── registration-service/
│   ├── feedback-service/               (optional)
│   └── notification-service/           (optional)
│
├── .kiro/
│   ├── steering/                       ← product.md, tech.md, platform-standards.md, structure.md
│   ├── specs/                          ← per-service specs
│   │   ├── user-service/
│   │   ├── event-service/
│   │   └── registration-service/
│   └── hooks/
│
├── services.yaml                       ← manifest for acceptance suite (copy of services.example.yaml)
├── services.example.yaml               ← DO NOT MODIFY
├── CHECKSUMS.sha256                    ← DO NOT MODIFY
├── BUGS.md                             ← bug log (exam requirement)
└── collaudo.txt                        ← acceptance suite output (exam requirement)
```

---

## Internal Structure of Each Service

Every service follows the same **clean architecture** layout:

```
services/<service-name>/
│
├── app/                        ← Python package (entry point: python -m app)
│   ├── __init__.py             ← create_app() factory
│   ├── __main__.py             ← reads PORT, calls create_app().run()
│   ├── config.py               ← reads ALL env vars in ONE place
│   ├── routes/                 ← Flask blueprints (HTTP layer only)
│   │   ├── __init__.py
│   │   ├── health.py
│   │   └── <resource>.py       ← e.g. users.py, events.py
│   ├── services/               ← business logic layer (pure Python, no Flask, no I/O)
│   │   ├── __init__.py
│   │   └── <resource>_service.py
│   ├── repositories/           ← persistence adapters (one per backend)
│   │   ├── __init__.py         ← get_repository(backend) factory
│   │   ├── base.py             ← AbstractRepository ABC
│   │   ├── memory.py
│   │   ├── json_repo.py
│   │   └── sqlite_repo.py
│   └── clients/                ← HTTP client wrappers for upstream services
│       ├── __init__.py
│       └── <upstream>_client.py  ← e.g. user_client.py, event_client.py
│
├── tests/
│   └── unit/                   ← pytest unit tests for this service
│       ├── conftest.py
│       ├── test_<resource>_memory.py
│       ├── test_<resource>_json.py
│       ├── test_<resource>_sqlite.py
│       └── test_contract_<resource>.py
│
├── requirements.txt            ← runtime deps: flask, requests
├── requirements-test.txt       ← test deps: pytest, pytest-cov, responses, PyYAML, jsonschema
└── pytest.ini                  ← testpaths = tests/unit, addopts = --cov=app
```

---

## Layer Responsibilities

### `config.py` — Configuration (single entry point for env vars)
- Reads `PORT`, `*_SERVICE_URL`, `STORAGE_BACKEND`, `DATA_DIR` once at import time.
- All other modules import from `config`, never from `os.environ` directly.
- Provides typed constants: `PORT: int`, `USER_SERVICE_URL: str`, etc.

### `routes/` — HTTP Layer
- Flask blueprints only. No business logic here.
- Responsibilities: parse request JSON, call service layer, serialize response, set status code and `Location` header.
- Handles `400` (malformed JSON via `request.get_json(force=True, silent=True)`).
- Returns `flask.jsonify(...)` with the correct status.

### `services/` — Business Logic Layer
- Pure Python functions/classes. No Flask, no `requests`, no I/O.
- All `REQ-*-B*` rules are enforced here.
- Calls the repository through the `AbstractRepository` interface.
- Calls upstream services through the client wrappers.
- Raises typed exceptions (e.g. `NotFoundError`, `ConflictError`, `ValidationError`, `DependencyUnavailableError`) that routes translate to HTTP responses.

### `repositories/` — Persistence Adapters
- `AbstractRepository` ABC defines the interface (CRUD + filters + pagination).
- `MemoryRepository`: plain `dict` — the default.
- `JsonRepository`: reads/writes a single JSON file; uses `threading.Lock` for thread-safety.
- `SqliteRepository`: uses `sqlite3`; creates the table on first use.
- `get_repository(backend, data_dir)` factory — called once in `create_app()`.
- Switching backend requires no change outside `config.py` + `create_app()`.

### `clients/` — External Service Clients
- One module per upstream service (e.g. `user_client.py`).
- Wraps `requests.get(url, timeout=2)` and translates responses:
  - `200` → returns parsed dict.
  - `404` → raises `ReferenceNotFoundError`.
  - `Timeout / ConnectionError / 5xx` → raises `DependencyUnavailableError`.
- URL built from `config.*_SERVICE_URL` — **never hard-coded**.
- Easily mockable in unit tests with `responses` library.

---

## Shared Code vs Duplication

**Decision:** NO shared library. Each service duplicates the small amount of common code
(error helpers, pagination helpers, timestamp utilities).

**Why:** The exam accepts services as independent Python packages. A shared library would
introduce coupling and complicate the `requirements.txt` setup without a build system. The
duplicated code (< 50 lines per service) is preferable to an implicit internal dependency.

If this were a production system with a second team, we'd publish the shared code as an
internal PyPI package — but that's out of scope for the exam.

---

## Configuration & Startup

- `config.py` is the **single place** that reads environment variables.
- `__main__.py` only does: `from app import create_app; create_app().run(host="0.0.0.0", port=config.PORT)`.
- `create_app()` wires blueprints and the repository; accepts optional overrides for testing.
- Start command in `services.yaml`: `python -m app` (same for all services).

---

## Test Organization

- **Unit tests** live inside `services/<svc>/tests/unit/`.
  - Run with: `pytest services/<svc>/tests/unit/ --cov=app`
  - Three test files per backend (`memory`, `json`, `sqlite`) using `tmp_path`.
  - At least 1 contract validation test per endpoint using `assert_matches_contract`.
  - Every test traceable to a `REQ-*` ID via docstring or `@pytest.mark.req("REQ-...")`.
- **Integration tests** (your own, not the acceptance suite) live in `services/<svc>/tests/integration/`.
  - Launch real service instances on free ports using `subprocess` or `threading`.
  - Cover: 1 happy path, 1 missing-reference 422, 1 dependency-offline 503.
- **Acceptance suite** is at `tests/integration/` (repo root) — **read-only, never modify**.
  - Run with: `pytest tests/integration -m mandatory -v`

Single command to run all unit tests across all services:
```bash
pytest services/ --cov=app --ignore=tests/integration
```

---

## Specs & Traceability

- One Kiro spec per service: `.kiro/specs/<service-name>/requirements.md|design.md|tasks.md`.
- `REQ-*` IDs defined in `requirements.md`, referenced in task comments, test docstrings, and commit messages.
- Finding `REQ-REG-B05`: `requirements.md` → `tasks.md` → `services/registration-service/app/services/registration_service.py` → `tests/unit/test_registration_memory.py`.

---

## Data & Git

- `data/` directories are in `.gitignore` (already present in template `.gitignore`).
- Commit sequence per service: `spec(<svc>): requirements` → `spec(<svc>): design` → `spec(<svc>): tasks` → `feat(<svc>): T-01 ...` → ... → `test(<svc>): unit tests`.
- No code before `tasks.md` commit — enforced by exam rules.

---

## Decision Log

| # | Decision | Alternative Considered | Reason Chosen |
|---|---|---|---|
| 1 | Monorepo | One repo per service | Acceptance suite runs from root |
| 2 | No shared lib | Internal PyPI package | No build system needed, < 50 lines duplication |
| 3 | Clean architecture (routes / services / repos / clients) | Fat routes | Testability: business logic testable without Flask or I/O |
| 4 | Abstract repository | Backend-specific service | Switching backend = 0 business logic changes |
| 5 | `config.py` single env-var reader | `os.environ` scattered | Single place to audit, easy to mock in tests |
| 6 | Unit tests inside `services/<svc>/tests/unit/` | Central `tests/` folder | Locality: tests travel with the service code |
| 7 | python -m app entrypoint | flask run / gunicorn | Matches `services.yaml` requirement, no extra tooling |
