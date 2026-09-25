# Design Document — user-service

**Spec:** user-service  
**Contract:** `contracts/openapi/user-service.yaml`  
**Requirements:** `.kiro/specs/user-service/requirements.md`

---

## Overview

`user-service` is a RESTful HTTP microservice that manages conference attendee/speaker/organizer profiles. It exposes a CRUD API under `/api/v1/users` (plus a `/health` endpoint) and is built with Flask following a clean three-layer architecture: HTTP layer → Service layer → Repository layer. Storage is pluggable at startup via the `STORAGE_BACKEND` environment variable, supporting in-memory, JSON-file, and SQLite backends without any change to business logic.

---

## Architecture

`user-service` follows a strict **clean architecture** with three concentric layers and a single direction of dependency (HTTP → Service → Repository interface):

```
┌──────────────────────────────────────────────┐
│           HTTP Layer  (Flask)                │
│  Routes / request parsing / response shaping │
├──────────────────────────────────────────────┤
│         Service Layer  (pure Python)         │
│  Business rules, validation, normalisation   │
├──────────────────────────────────────────────┤
│        Repository Layer  (adapters)          │
│  memory · json · sqlite3  — I/O only here    │
└──────────────────────────────────────────────┘
```

The concrete repository adapter is injected at application startup via the `create_app(repo)` factory. Neither the service layer nor the HTTP layer imports a concrete adapter directly; they depend only on the abstract `UserRepository` interface.

---

## Components and Interfaces

### HTTP Layer (Flask Blueprint `users`)

Accepts HTTP requests, delegates all decisions to the service layer, and translates service return values / exceptions into HTTP responses. Route functions must not contain business logic or storage access.

| Method | Path | Route function | Service call |
|---|---|---|---|
| POST | `/api/v1/users` | `create_user()` | `svc.create(data)` |
| GET | `/api/v1/users` | `list_users()` | `svc.list(filters, page, page_size)` |
| GET | `/api/v1/users/<id>` | `get_user(id)` | `svc.get(id)` |
| PUT | `/api/v1/users/<id>` | `replace_user(id)` | `svc.replace(id, data)` |
| PATCH | `/api/v1/users/<id>` | `update_user(id)` | `svc.update(id, data)` |
| DELETE | `/api/v1/users/<id>` | `delete_user(id)` | `svc.delete(id)` |
| GET | `/health` | `health()` | _(inline)_ |

### Service Layer — `UserService(repo: UserRepository)`

Implements all business rules (email uniqueness, field validation, normalisation, pagination). Has zero I/O — interacts with storage exclusively through the repository interface.

### Repository Layer — `UserRepository` (ABC)

```python
class UserRepository(ABC):
    def insert(self, user: dict) -> dict: ...
    def find_by_id(self, id: str) -> dict | None: ...
    def find_all(self, filters: dict | None = None) -> list[dict]: ...
    def update(self, id: str, data: dict) -> dict | None: ...
    def delete(self, id: str) -> bool: ...
    def email_exists(self, email: str, exclude_id: str | None = None) -> bool: ...
```

Three concrete adapters implement this interface: `MemoryRepository`, `JsonRepository`, `Sqlite3Repository`.

---

## Data Models

### `User` (stored and returned shape)

```python
{
    "id":         str,   # UUID v4
    "first_name": str,   # 1–50 chars
    "last_name":  str,   # 1–50 chars
    "email":      str,   # lowercase-normalised, unique across all users
    "company":    str | None,  # max 100 chars, nullable
    "role":       str,   # "attendee" | "speaker" | "organizer"
    "created_at": str,   # ISO 8601 UTC, e.g. "2026-10-01T10:00:00Z"
    "updated_at": str,   # ISO 8601 UTC
}
```

### `UserCreate` (POST / PUT request body)

Required fields: `first_name`, `last_name`, `email`, `role`. Optional: `company`. `additionalProperties: false` — unknown keys are rejected with 422.

### `UserUpdate` (PATCH request body)

All fields optional, but at least one must be present. Same field-level constraints as `UserCreate`.

### `UserPage` (GET /api/v1/users response)

```python
{
    "items":     list[User],
    "page":      int,   # ≥ 1
    "page_size": int,   # 1–100
    "total":     int,
}
```

### `Error` (all 4xx responses)

```json
{ "error": { "code": "UPPER_SNAKE_CASE", "message": "...", "details": {} } }
```

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Layer Breakdown](#2-layer-breakdown)
   - 2.1 [HTTP Layer (Flask routes)](#21-http-layer-flask-routes)
   - 2.2 [Service Layer (business logic)](#22-service-layer-business-logic)
   - 2.3 [Repository Layer (storage adapters)](#23-repository-layer-storage-adapters)
3. [Module & File Structure](#3-module--file-structure)
4. [Storage Switching](#4-storage-switching)
5. [Data Model](#5-data-model)
6. [Contract Alignment](#6-contract-alignment)
7. [Error Handling](#7-error-handling)
8. [Unit Testing Strategy](#8-unit-testing-strategy)
9. [Non-Functional Considerations](#9-non-functional-considerations)

---

## 1. Architecture Overview

`user-service` follows a strict **clean architecture** with three concentric layers:

```
┌──────────────────────────────────────────────┐
│           HTTP Layer  (Flask)                │
│  Routes / request parsing / response shaping │
├──────────────────────────────────────────────┤
│         Service Layer  (pure Python)         │
│  Business rules, validation, normalisation   │
├──────────────────────────────────────────────┤
│        Repository Layer  (adapters)          │
│  memory · json · sqlite3  — I/O only here    │
└──────────────────────────────────────────────┘
```

**Dependency direction:** HTTP → Service → Repository interface.  
Neither the service layer nor the HTTP layer imports a concrete adapter directly; they depend only on the abstract `UserRepository` interface. The concrete adapter is injected at application startup via the factory function `create_app(repo)`.

---

## 2. Layer Breakdown

### 2.1 HTTP Layer (Flask routes)

**Responsibility:** Accept HTTP requests, delegate all decisions to the service layer, translate service return values / exceptions into HTTP responses.

**What it does:**
- Parse the request body (`request.get_json(force=True, silent=True)`) and query parameters.
- Call the appropriate service method, passing only plain Python types.
- Map service results to JSON responses with the correct status code and headers (e.g. `Location` header on 201).
- Map service exceptions to the error envelope defined in the contract (see §7).

**What it must NOT do:**
- Validate business rules.
- Access the storage backend.
- Know about the difference between storage adapters.

**Endpoints and their Flask route functions:**

| Method | Path | Route function | Service call |
|---|---|---|---|
| POST | `/api/v1/users` | `create_user()` | `svc.create(data)` |
| GET | `/api/v1/users` | `list_users()` | `svc.list(filters, page, page_size)` |
| GET | `/api/v1/users/<id>` | `get_user(id)` | `svc.get(id)` |
| PUT | `/api/v1/users/<id>` | `replace_user(id)` | `svc.replace(id, data)` |
| PATCH | `/api/v1/users/<id>` | `update_user(id)` | `svc.update(id, data)` |
| DELETE | `/api/v1/users/<id>` | `delete_user(id)` | `svc.delete(id)` |
| GET | `/health` | `health()` | _(inline, no service call)_ |

Routes are registered on a Flask `Blueprint` named `users`. The `create_app` factory attaches the blueprint after injecting the repository into the service.

---

### 2.2 Service Layer (business logic)

**Responsibility:** Implement all business rules from the requirements. Has zero I/O — it reads and writes data exclusively through the repository interface.

**Class:** `UserService(repo: UserRepository)`

**Methods:**

| Method | Key logic |
|---|---|
| `create(data: dict) -> dict` | Validate `UserCreate` fields; normalise email to lowercase; enforce email uniqueness (REQ-USR-B01/B02); generate UUID v4 `id`; set `created_at` / `updated_at`; delegate to `repo.insert`. |
| `list(filters: dict, page: int, page_size: int) -> dict` | Validate `page ≥ 1`, `1 ≤ page_size ≤ 100`; delegate filtered fetch to `repo.find_all`; slice for pagination; return `UserPage` dict. |
| `get(id: str) -> dict` | Delegate to `repo.find_by_id`; raise `NotFoundError` if absent. |
| `replace(id: str, data: dict) -> dict` | Validate `UserCreate` fields; normalise email; enforce email uniqueness excluding self; delegate to `repo.update`; set `updated_at`. |
| `update(id: str, data: dict) -> dict` | Validate `UserUpdate` fields (at least one present); normalise email if supplied; enforce email uniqueness excluding self; delegate to `repo.patch`; set `updated_at`. |
| `delete(id: str) -> None` | Delegate to `repo.delete`; raise `NotFoundError` if absent. |

**Internal validation helpers** (pure functions, no I/O):

- `_validate_create(data)` — checks required fields, lengths, email format, known-keys-only (`additionalProperties: false`).
- `_validate_update(data)` — checks at least one field present, same field-level rules.
- `_validate_role(value)` — checks value is in `{attendee, speaker, organizer}`.
- `_normalise_email(email)` → `email.strip().lower()`

**Service exceptions** (defined in `service/exceptions.py`):

| Exception | HTTP status | Error code |
|---|---|---|
| `ValidationError(message)` | 422 | `VALIDATION_ERROR` |
| `MalformedJsonError` | 400 | `MALFORMED_JSON` |
| `EmailConflictError` | 409 | `EMAIL_ALREADY_EXISTS` |
| `NotFoundError` | 404 | `NOT_FOUND` |

All exceptions carry a `code` attribute matching the contract's `UPPER_SNAKE_CASE` codes.

---

### 2.3 Repository Layer (storage adapters)

**Responsibility:** Provide CRUD access to user records. Every adapter implements the same abstract interface; the service layer calls only interface methods.

#### Abstract interface — `UserRepository`

```python
class UserRepository(ABC):
    def insert(self, user: dict) -> dict: ...
    def find_by_id(self, id: str) -> dict | None: ...
    def find_all(self, filters: dict | None = None) -> list[dict]: ...
    def update(self, id: str, data: dict) -> dict | None: ...
    def delete(self, id: str) -> bool: ...
    def email_exists(self, email: str, exclude_id: str | None = None) -> bool: ...
```

All methods receive and return plain `dict` objects (the serialised `User` shape). No adapter leaks its internal representation to callers.

#### Adapter 1 — `MemoryRepository`

- Stores users in an in-process `dict[str, dict]` keyed by `id`.
- No external dependencies. Used as the default in development and the test baseline.
- Not persistent across process restarts.

#### Adapter 2 — `JsonRepository`

- Persists a single JSON file at `{DATA_DIR}/users.json`.
- Reads the file on every read operation; writes the full file on every write.
- `DATA_DIR` is resolved from the environment variable (see §4).
- Handles concurrent-write safety with a `threading.Lock`.

#### Adapter 3 — `Sqlite3Repository`

- Persists a SQLite database at `{DATA_DIR}/users.db`.
- Uses Python's built-in `sqlite3` module; no ORM.
- Schema is created with `CREATE TABLE IF NOT EXISTS users (...)` on first connection.
- Column layout mirrors the `User` schema fields; `id` is the primary key (TEXT).
- All read/write operations use parameterised queries to prevent injection.

---

## 3. Module & File Structure

```
user-service/
├── app.py                  # create_app(repo) factory + entry-point
├── routes/
│   └── users.py            # Flask Blueprint with all route functions
├── service/
│   ├── user_service.py     # UserService class
│   └── exceptions.py       # Domain exceptions
├── repository/
│   ├── base.py             # UserRepository ABC
│   ├── memory.py           # MemoryRepository
│   ├── json_repo.py        # JsonRepository
│   └── sqlite_repo.py      # Sqlite3Repository
└── tests/
    ├── conftest.py          # backend_repo fixture (parametrized)
    ├── test_routes_users.py # HTTP-layer tests (via Flask test client)
    ├── test_service.py      # Service-layer unit tests
    └── test_repository.py   # Repository-layer unit tests
```

> The `user-service/` directory lives inside the workspace root alongside the other services.

---

## 4. Storage Switching

Storage selection is driven by two environment variables:

| Variable | Purpose | Default |
|---|---|---|
| `STORAGE_BACKEND` | Selects the adapter: `memory`, `json`, or `sqlite` | `memory` |
| `DATA_DIR` | Filesystem path used by `json` and `sqlite` adapters | `./data` |
| `PORT` | Port the Flask dev server binds to | `5001` |

The factory in `app.py` performs adapter selection at startup:

```python
def _build_repo() -> UserRepository:
    backend = os.environ.get("STORAGE_BACKEND", "memory").lower()
    data_dir = Path(os.environ.get("DATA_DIR", "./data"))
    if backend == "memory":
        return MemoryRepository()
    if backend == "json":
        data_dir.mkdir(parents=True, exist_ok=True)
        return JsonRepository(data_dir / "users.json")
    if backend == "sqlite":
        data_dir.mkdir(parents=True, exist_ok=True)
        return Sqlite3Repository(data_dir / "users.db")
    raise ValueError(f"Unknown STORAGE_BACKEND: {backend!r}")
```

**Isolation guarantee:** `_build_repo` is the only place that reads `STORAGE_BACKEND`. The `UserService` and all route functions receive a `UserRepository` instance and never inspect the environment. Switching backends requires only changing the environment variable — no route or business-logic module is modified.

---

## 5. Data Model

### In-memory representation (all adapters normalise to this shape)

```python
{
    "id":         str,   # UUID v4
    "first_name": str,   # 1–50 chars
    "last_name":  str,   # 1–50 chars
    "email":      str,   # lowercase-normalised, unique
    "company":    str | None,  # max 100 chars, nullable
    "role":       str,   # "attendee" | "speaker" | "organizer"
    "created_at": str,   # ISO 8601 UTC, e.g. "2026-10-01T10:00:00Z"
    "updated_at": str,   # ISO 8601 UTC
}
```

All timestamps are generated with `datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")` in the service layer before being passed to the repository.

---

## 6. Contract Alignment

The implementation is required to conform to `contracts/openapi/user-service.yaml` at every response boundary. Key alignment points:

### Schemas enforced at runtime

| Contract schema | Enforced by |
|---|---|
| `UserCreate` | `_validate_create()` in service layer — required fields, lengths, `additionalProperties: false` |
| `UserUpdate` | `_validate_update()` in service layer |
| `User` | Constructed from the stored dict; all seven required fields always present |
| `UserPage` | Assembled in `svc.list()`; keys `items`, `page`, `page_size`, `total` always present |
| `Error` | Built by the Flask error handler from service exceptions; outer `error` key with `code` and `message` always present |
| `Health` | Returned inline from the `/health` route |

### `additionalProperties: false` compliance

- `UserCreate` and `UserUpdate` validation rejects any key not in the allowed set, responding `422 VALIDATION_ERROR`.
- `User` responses are built by whitelisting only the eight known fields — no extra keys can leak through.
- `Error` responses are built from a fixed template; no additional keys are ever added.

### Location header (REQ-USR-E01 AC2)

The `POST /api/v1/users` route sets `Location: /api/v1/users/{id}` in the 201 response, matching the contract's `headers.Location` declaration.

### Pagination parameters

The `page` and `page_size` query parameters are declared with `minimum`, `maximum`, and `default` in the contract. The service layer enforces the same bounds and defaults without relying on OpenAPI middleware.

### Contract validation in tests

Every test that exercises an HTTP route calls `assert_matches_contract` from `contracts/validator.py` to verify the response body against the live OpenAPI spec (see §8).

---

## 7. Error Handling

All 4xx error responses use the contract's `Error` envelope:

```json
{
  "error": {
    "code": "UPPER_SNAKE_CASE",
    "message": "Human-readable description",
    "details": {}
  }
}
```

A single Flask `@app.errorhandler` catches each domain exception type and maps it to the correct status and code. No error-handling logic lives inside individual route functions. The mapping is:

| Exception type | Status | `code` |
|---|---|---|
| `MalformedJsonError` | 400 | `MALFORMED_JSON` |
| `ValidationError` | 422 | `VALIDATION_ERROR` |
| `EmailConflictError` | 409 | `EMAIL_ALREADY_EXISTS` |
| `NotFoundError` | 404 | `NOT_FOUND` |

Unhandled exceptions (5xx) are left to Flask's default handler so they surface clearly during testing.

---

## 8. Unit Testing Strategy

### Framework and tooling

| Tool | Role |
|---|---|
| `pytest` | Test runner |
| `pytest-cov` | Coverage measurement |
| Flask test client (`app.test_client()`) | HTTP-layer testing without a live server |
| `contracts/validator.py::assert_matches_contract` | Response contract assertion |
| `tmp_path` (pytest built-in fixture) | Isolated filesystem for `json` and `sqlite` adapters |

### Parameterised backend fixture

All tests that exercise storage-touching code are parameterised across all three backends via a shared `conftest.py` fixture:

```python
# tests/conftest.py
import pytest
from repository.memory import MemoryRepository
from repository.json_repo import JsonRepository
from repository.sqlite_repo import Sqlite3Repository

@pytest.fixture(params=["memory", "json", "sqlite"])
def backend_repo(request, tmp_path):
    if request.param == "memory":
        return MemoryRepository()
    if request.param == "json":
        return JsonRepository(tmp_path / "users.json")
    if request.param == "sqlite":
        return Sqlite3Repository(tmp_path / "users.db")
```

Each test function that declares `backend_repo` as a parameter is automatically run three times — once per adapter. `tmp_path` guarantees that each run starts with a clean, isolated directory.

### Test modules

**`test_repository.py`** — repository interface contract tests

- Verifies that every adapter satisfies the `UserRepository` contract identically.
- Tests: `insert`, `find_by_id`, `find_all` (with and without filters), `update`, `delete`, `email_exists`.
- All tests parametrised via `backend_repo`.

**`test_service.py`** — service layer unit tests

- Uses `MemoryRepository` (or `backend_repo` for storage-sensitive cases).
- Tests each business rule in isolation: email normalisation, uniqueness, validation errors, pagination bounds, filter logic.
- No Flask test client involved — calls `UserService` methods directly.

**`test_routes_users.py`** — HTTP integration tests

- Parametrised via `backend_repo`; each test creates a fresh `create_app(repo)` instance.
- Uses the Flask test client to issue real HTTP requests.
- Every successful response is followed by `assert_matches_contract(...)`:

```python
from contracts.validator import assert_matches_contract

def test_create_user_201(client):
    resp = client.post("/api/v1/users", json={
        "first_name": "Alice", "last_name": "Smith", "email": "alice@example.com"
    })
    assert resp.status_code == 201
    assert_matches_contract("user-service", "POST", "/api/v1/users", resp)
    assert resp.headers["Location"] == f"/api/v1/users/{resp.json['id']}"
```

- Error responses (400, 404, 409, 422) are also validated against the contract.

### Coverage target

- Target: **≥ 80% line coverage** across the entire `user-service` package, measured across all three backends.
- Run with: `pytest --cov=. --cov-report=term-missing`
- At least one contract-asserting test exists for every endpoint (REQ-USR-N06).

### Test cases per endpoint (minimum set)

| Endpoint | Happy path | Error paths |
|---|---|---|
| `POST /api/v1/users` | 201 + Location header + contract | 400, 409, 422 (missing field), 422 (extra field) |
| `GET /api/v1/users` | 200 + contract | 422 (bad page), 422 (bad role) |
| `GET /api/v1/users/{id}` | 200 + contract | 404 |
| `PUT /api/v1/users/{id}` | 200 + contract | 404, 409, 422 |
| `PATCH /api/v1/users/{id}` | 200 + contract | 404, 409, 422 |
| `DELETE /api/v1/users/{id}` | 204 + contract | 404 |
| `GET /health` | 200 + contract | — |

---

## 9. Non-Functional Considerations

| Requirement | Design decision |
|---|---|
| REQ-USR-N01 — `PORT` env var | `app.run(port=int(os.environ.get("PORT", 5001)))` in `app.py` entry-point. |
| REQ-USR-N02/N03 — `STORAGE_BACKEND` switching | Handled entirely in `_build_repo()`; zero leakage into routes or service. |
| REQ-USR-N04 — No outbound HTTP | No `requests` / `httpx` import anywhere in the service package. |
| REQ-USR-N05 — ≥ 80% coverage | Enforced via `pytest --cov` with parameterised backend fixture (§8). |
| REQ-USR-N06 — Contract assertion per endpoint | Guaranteed by test structure: every happy-path route test calls `assert_matches_contract`. |


---

## Correctness Properties

The following invariants must hold at all times:

| Property | Description |
|---|---|
| Email uniqueness | No two `User` records in any adapter may share the same normalised (lowercase-trimmed) email address. |
| Email normalisation | Every email stored and returned by the service is lowercase and stripped of leading/trailing whitespace. |
| Immutable `id` | The `id` (UUID v4) assigned at creation is never modified by `replace` or `update` operations. |
| Immutable `created_at` | `created_at` is set once at creation and never overwritten by subsequent writes. |
| `updated_at` monotonicity | `updated_at` is always ≥ `created_at` and is refreshed on every successful `replace` or `update`. |
| Pagination bounds | `page` ≥ 1 and 1 ≤ `page_size` ≤ 100 are enforced; out-of-range values always return 422. |
| No extra fields in responses | `User`, `UserPage`, `Error`, and `Health` responses contain only the fields declared in the OpenAPI contract (`additionalProperties: false`). |
| Adapter interchangeability | Switching `STORAGE_BACKEND` between `memory`, `json`, and `sqlite` must produce identical observable behaviour for every API operation. |

---

## Error Handling

All client errors use the contract `Error` envelope:

```json
{ "error": { "code": "UPPER_SNAKE_CASE", "message": "Human-readable description", "details": {} } }
```

A single Flask `@app.errorhandler` per exception type maps domain exceptions to HTTP status codes. No error-handling logic lives inside individual route functions.

| Exception | HTTP status | `code` |
|---|---|---|
| `MalformedJsonError` | 400 | `MALFORMED_JSON` |
| `ValidationError` | 422 | `VALIDATION_ERROR` |
| `EmailConflictError` | 409 | `EMAIL_ALREADY_EXISTS` |
| `NotFoundError` | 404 | `NOT_FOUND` |

Unhandled exceptions (5xx) are left to Flask's default handler so they surface clearly during testing and are never silently swallowed.

---

## Testing Strategy

### Framework and tooling

| Tool | Role |
|---|---|
| `pytest` | Test runner |
| `pytest-cov` | Coverage measurement (target ≥ 80% line coverage) |
| Flask test client (`app.test_client()`) | HTTP-layer tests without a live server |
| `contracts/validator.py::assert_matches_contract` | Response contract assertion for every happy-path endpoint test |
| `tmp_path` (pytest built-in) | Isolated filesystem for `json` and `sqlite` adapters |

### Parameterised backend fixture

Tests that touch storage are parameterised across all three adapters via a `conftest.py` fixture, ensuring adapter interchangeability is verified automatically:

```python
@pytest.fixture(params=["memory", "json", "sqlite"])
def backend_repo(request, tmp_path):
    if request.param == "memory":  return MemoryRepository()
    if request.param == "json":    return JsonRepository(tmp_path / "users.json")
    if request.param == "sqlite":  return Sqlite3Repository(tmp_path / "users.db")
```

### Test modules

- **`test_repository.py`** — verifies the `UserRepository` contract identically across all three adapters.
- **`test_service.py`** — unit-tests business rules (validation, normalisation, uniqueness, pagination) by calling `UserService` directly against `MemoryRepository`.
- **`test_routes_users.py`** — HTTP integration tests via the Flask test client; every successful response is asserted against the OpenAPI contract with `assert_matches_contract`.

### Minimum test coverage per endpoint

| Endpoint | Happy path | Error paths |
|---|---|---|
| `POST /api/v1/users` | 201 + Location header | 400, 409, 422 (missing/extra field) |
| `GET /api/v1/users` | 200 | 422 (bad page, bad role filter) |
| `GET /api/v1/users/{id}` | 200 | 404 |
| `PUT /api/v1/users/{id}` | 200 | 404, 409, 422 |
| `PATCH /api/v1/users/{id}` | 200 | 404, 409, 422 |
| `DELETE /api/v1/users/{id}` | 204 | 404 |
| `GET /health` | 200 | — |
