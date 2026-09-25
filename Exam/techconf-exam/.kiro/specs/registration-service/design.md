# registration-service — Design

**Requirements:** `.kiro/specs/registration-service/requirements.md`  
**Contract:** `contracts/openapi/registration-service.yaml`  
**Repository standards:** `.kiro/steering/structure.md`, `.kiro/steering/platform-standards.md`

---

## 1. Architecture Goals

The registration-service coordinates local registration state with user-service and event-service. Its design separates HTTP transport, orchestration/business rules, persistence, and upstream clients so each concern can be tested independently.

Key goals:

1. Match every request and response declared by the registration OpenAPI contract.
2. Keep REQ-REG-B01 through REQ-REG-B09 in `RegistrationService` and explicit application ports.
3. Prevent duplicate confirmed registrations and capacity overflow atomically across memory, JSON, and SQLite.
4. Read every port, backend, data path, and dependency URL from centralized configuration.
5. Translate upstream 404 and availability failures according to operation context.
6. Support isolated unit tests plus real-HTTP cross-service tests and at least 80% application coverage.

---

## 2. Layered Architecture

```text
Client
  │
  ▼
Flask routes / error handlers
  │
  ▼
RegistrationService
  ├──────────────────┬───────────────────┐
  ▼                  ▼                   ▼
RegistrationRepository  UserClient       EventClient
  │                      │                   │
  ├─ Memory              └─ user-service     └─ event-service
  ├─ JSON
  └─ SQLite
```

Dependency direction:

- Routes depend on `RegistrationService` only.
- `RegistrationService` depends on repository and dependency-client interfaces.
- Storage and HTTP adapters implement those interfaces.
- Business logic does not import Flask, `requests`, filesystem modules, `sqlite3`, or concrete adapters.
- registration-service never imports Python modules from user-service or event-service.

---

## 3. Repository Layout

```text
services/registration-service/
├── app/
│   ├── __init__.py                       # create_app and dependency wiring
│   ├── __main__.py                       # python -m app
│   ├── config.py                         # all environment reads
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── health.py
│   │   └── registrations.py              # collection, item, stats, explicit PUT
│   ├── services/
│   │   ├── __init__.py
│   │   ├── exceptions.py
│   │   └── registration_service.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── registration_repository.py    # persistence port and reservation outcomes
│   │   ├── memory.py
│   │   ├── json_repo.py
│   │   └── sqlite_repo.py
│   └── clients/
│       ├── __init__.py
│       ├── user_client.py                # interface + HTTP implementation
│       └── event_client.py               # interface + HTTP implementation
├── tests/
│   ├── unit/
│   │   ├── test_registration_repository.py
│   │   ├── test_registration_service.py
│   │   ├── test_dependency_clients.py
│   │   └── test_routes_registrations.py
│   ├── integration/
│   │   └── test_cross_service_registration.py
│   └── conftest.py
├── requirements.txt
├── requirements-test.txt
└── pytest.ini
```

---

## 4. Configuration and Composition

### 4.1 Central settings

`app/config.py` is the only environment reader.

| Setting | Variable | Default |
|---|---|---|
| Listening port | `PORT` | `5003` |
| user-service URL | `USER_SERVICE_URL` | `http://localhost:5001` |
| event-service URL | `EVENT_SERVICE_URL` | `http://localhost:5002` |
| Backend | `STORAGE_BACKEND` | `memory` |
| Persistence directory | `DATA_DIR` | `./data` |
| Dependency timeout | Internal setting | 2 seconds |

URLs are normalized by removing trailing slashes. Dependency paths are appended by the HTTP clients. No acceptance port is embedded in application code.

### 4.2 Application factory

`create_app` performs dependency composition:

1. Load or accept settings.
2. Build or accept an injected `RegistrationRepository`.
3. Build or accept injected `UserClient` and `EventClient` implementations.
4. Construct `RegistrationService`.
5. Register registration and health blueprints.
6. Register domain error handlers and the JSON 405 behavior.

Tests inject repositories and fake clients. Normal startup selects adapters from environment settings.

### 4.3 Entry point

`app/__main__.py` starts the application on `0.0.0.0` and the configured port. `services.yaml` launches it from `services/registration-service` with `python -m app`.

---

## 5. Domain Model

A stored registration contains exactly:

| Field | Representation | Ownership |
|---|---|---|
| `id` | Canonical UUID v4 string | Server-generated |
| `user_id` | Canonical UUID string | POST input, immutable |
| `event_id` | Canonical UUID string | POST input, immutable |
| `amount` | JSON number | Copied once from event price |
| `status` | `confirmed` or `cancelled` | Created confirmed; only cancellation allowed |
| `created_at` | ISO 8601 UTC string ending `Z` | Immutable |
| `updated_at` | ISO 8601 UTC string ending `Z` | Refreshed on cancellation |

Response projection uses an explicit allowlist to ensure `additionalProperties: false`. No upstream response object or internal repository metadata is stored.

---

## 6. RegistrationRepository and Atomicity

### 6.1 Repository operations

The persistence port supports:

| Operation | Purpose |
|---|---|
| Find by ID | GET, PATCH, DELETE |
| Find all with filters | List and pagination |
| Insert confirmed atomically | Duplicate and capacity enforcement plus creation |
| Update status | Cancellation |
| Delete | Resource deletion |
| Count confirmed by event | Statistics |

Atomic insertion receives the complete registration and validated event capacity. It evaluates confirmed duplicates and confirmed event count inside the same backend critical section/transaction and returns one of three outcomes: `created`, `already_registered`, or `event_full`. `RegistrationService` maps outcomes to domain exceptions. This keeps HTTP/business error selection in the service while making the capacity invariant race-safe.

Duplicate evaluation precedes capacity evaluation so a repeated confirmed registration consistently yields `ALREADY_REGISTERED`, even when the event is full.

### 6.2 Memory adapter

- Dictionary keyed by registration ID.
- Re-entrant lock surrounds duplicate check, capacity count, and insertion.
- Filters by `user_id`, `event_id`, and `status` with logical AND.
- Returns defensive copies.

### 6.3 JSON adapter

- Persists `$DATA_DIR/registrations.json` using standard-library `json` and file APIs.
- Lock surrounds each complete read-modify-write transaction.
- Writes to a temporary file and atomically replaces the target.
- Performs duplicate/capacity checks before the same locked write.
- Returns the same dictionary shapes and outcomes as memory.

### 6.4 SQLite adapter

- Persists `$DATA_DIR/registrations.db` with standard-library `sqlite3`.
- Creates a table whose columns match the registration resource.
- Uses parameterized SQL exclusively.
- Uses an immediate transaction for confirmed duplicate/count/insert operations.
- Uses a partial unique index on `(user_id, event_id)` where status is `confirmed` as a second duplicate safeguard.
- Counts only `status='confirmed'` for capacity and statistics.

---

## 7. Dependency Client Design

### 7.1 UserClient

`UserClient.get_user(user_id)` calls `GET /api/v1/users/{id}` and returns a plain user dictionary.

- `200` with usable JSON: success.
- `404`: raise a typed upstream-reference-not-found signal.
- Timeout, connection failure, 5xx, unexpected status, or unusable JSON: raise `DependencyUnavailableError` naming user-service.

### 7.2 EventClient

`EventClient.get_event(event_id)` calls `GET /api/v1/events/{id}` and returns a plain event dictionary containing at least `id`, `status`, `capacity`, and `price`.

- `200` with usable JSON: success.
- `404`: raise a typed upstream-reference-not-found signal.
- Timeout, connection failure, 5xx, unexpected status, or unusable JSON: raise `DependencyUnavailableError` naming event-service.

### 7.3 Context-sensitive 404 translation

The clients report an upstream not-found signal without selecting the final HTTP response. `RegistrationService` maps it according to the operation:

| Operation | Missing upstream object | Public result |
|---|---|---|
| Create | User missing | 422 `REFERENCE_NOT_FOUND` |
| Create | Event missing | 422 `REFERENCE_NOT_FOUND` |
| Stats | Event missing | 404 `NOT_FOUND` |

All calls use timeout 2 seconds and base URLs injected from centralized settings.

---

## 8. RegistrationService Behavior

### 8.1 Create flow

Validation and orchestration order:

1. Require a JSON object with exactly `user_id` and `event_id`.
2. Validate both as canonical UUID strings.
3. Verify user existence through `UserClient`.
4. Fetch event through `EventClient`.
5. Require event status `published`.
6. Validate event `capacity` and `price` as usable values.
7. Generate registration ID, captured amount, confirmed status, and timestamps.
8. Ask the repository to atomically insert subject to duplicate and capacity constraints.
9. Map atomic outcome to success, `ALREADY_REGISTERED`, or `EVENT_FULL`.

No local write occurs before both dependency checks succeed.

### 8.2 List flow

- Validate `page >= 1` and `1 <= page_size <= 100`.
- Validate optional `user_id` and `event_id` UUID filters.
- Validate optional status as `confirmed` or `cancelled`.
- Apply all supplied filters before slicing.
- Return `items`, `page`, `page_size`, and filtered pre-slice `total`.
- Do not call dependencies.

### 8.3 Get, cancellation, and delete

- Get returns a local record or raises local `NOT_FOUND`.
- PATCH accepts only `{"status":"cancelled"}`.
- Only `confirmed→cancelled` is allowed; all other assignments raise `INVALID_STATUS_TRANSITION`.
- Cancellation preserves identity, references, amount, and creation time and refreshes `updated_at`.
- Cancelled registrations immediately stop contributing to duplicate and capacity checks.
- Delete removes any existing registration or raises local `NOT_FOUND`.
- These operations do not call dependencies.

### 8.4 Statistics flow

1. Require and validate `event_id`.
2. Fetch the event through `EventClient`.
3. Translate missing event to local 404 `NOT_FOUND`.
4. Count confirmed registrations locally.
5. Return event capacity, confirmed count, and non-negative available count.

Statistics do not require user-service and include cancelled records in neither `confirmed` nor availability consumption.

---

## 9. HTTP Layer

### 9.1 Routes

| Method | Path | Success |
|---|---|---:|
| POST | `/api/v1/registrations` | 201 + `Location` |
| GET | `/api/v1/registrations` | 200 paginated page |
| GET | `/api/v1/registrations/stats` | 200 statistics |
| GET | `/api/v1/registrations/{id}` | 200 registration |
| PATCH | `/api/v1/registrations/{id}` | 200 cancelled registration |
| DELETE | `/api/v1/registrations/{id}` | 204 empty body |
| PUT | `/api/v1/registrations/{id}` | 405 JSON error |
| GET | `/health` | 200 health body |

The static `/stats` route is registered explicitly and never interpreted as a registration ID.

### 9.2 Request/response handling

- Routes distinguish malformed JSON from valid JSON with an invalid shape.
- Routes parse query strings and pass plain values to the service.
- POST sets relative `Location: /api/v1/registrations/{id}`.
- DELETE produces a truly empty body.
- PUT has an explicit handler so Flask does not return its default HTML 405 page.
- Health reports only local process health and never probes dependencies.

---

## 10. Error Handling

Central error handlers map typed exceptions to the strict envelope.

| Domain exception | Status | Code |
|---|---:|---|
| Malformed JSON | 400 | `MALFORMED_JSON` |
| Local/statistics not found | 404 | `NOT_FOUND` |
| Already registered | 409 | `ALREADY_REGISTERED` |
| Event full | 409 | `EVENT_FULL` |
| Validation | 422 | `VALIDATION_ERROR` |
| Missing create reference | 422 | `REFERENCE_NOT_FOUND` |
| Event not open | 422 | `EVENT_NOT_OPEN` |
| Invalid status transition | 422 | `INVALID_STATUS_TRANSITION` |
| Method not allowed | 405 | `METHOD_NOT_ALLOWED` |
| Dependency unavailable | 503 | `DEPENDENCY_UNAVAILABLE` |

Every response includes `error.code`, `error.message`, and an object-valued `error.details`. Stack traces and raw upstream errors are never exposed.

---

## 11. Contract Alignment

| OpenAPI schema/operation | Enforcement |
|---|---|
| `RegistrationCreate` | Exact POST allowlist and UUID validation |
| `RegistrationPatch` | Exact required status-only PATCH body |
| `Registration` | Explicit seven-field projection |
| `RegistrationPage` | Service pagination envelope |
| `RegistrationStats` | Service stats projection |
| `Health` | Dedicated health route |
| `Error` | Central JSON exception handlers |
| PUT 405 | Explicit route and error envelope |
| POST `Location` | Set by successful creation route |
| `additionalProperties: false` | Request key checks and response allowlists |

The implementation and its tests import but never modify `contracts/validator.py`. Protected contracts, acceptance tests, and checksums remain read-only.

---

## 12. Testing Strategy

### 12.1 Repository tests

A parameterized fixture runs the same repository contract against memory, JSON, and SQLite with `tmp_path` for files. Tests cover CRUD, combined filters, confirmed counting, cancellation seat release, duplicate outcomes, full outcomes, and atomic behavior.

### 12.2 Service tests

Fake user/event clients verify:

- User and event reference handling.
- Published-event requirement.
- Amount copied from event price.
- Duplicate-before-full precedence.
- Capacity and cancelled-seat behavior.
- Status transition restrictions.
- List filters and pagination.
- Statistics and context-specific event 404.
- No local mutation on failed dependencies.

### 12.3 HTTP client tests

`responses` mocks both dependencies and covers configured URL composition, 200, 404, 5xx, unexpected status, malformed/unusable JSON, timeout, and connection errors.

### 12.4 Route and contract tests

Flask `test_client` tests every endpoint against all three repositories. At least one response per endpoint is adapted to `contracts.validator::assert_matches_contract`; declared error response families are also contract-checked. Location, empty 204 body, strict 405 JSON, pagination, and error codes receive explicit assertions.

### 12.5 Custom integration tests

Real HTTP user, event, and registration processes/servers run on free ports with reliable cleanup. Minimum scenarios:

1. Existing user + published event + available capacity → 201 confirmed registration with copied amount.
2. Missing user or event → 422 `REFERENCE_NOT_FOUND`.
3. Stopped dependency → 503 `DEPENDENCY_UNAVAILABLE`.

### 12.6 Coverage and traceability

- Run all tests with `pytest --cov=app --cov-report=term-missing --cov-fail-under=80`.
- Exercise all three persistence backends.
- Attach `REQ-REG-*` IDs through pytest markers, names, or docstrings.

---

## 13. Requirement Traceability

| Requirements | Primary components | Main verification |
|---|---|---|
| REQ-REG-B01, B02, B03, B06, B09 | RegistrationService, dependency clients | Service/client/integration tests |
| REQ-REG-B04, B05 | RegistrationService, atomic repository insertion | Service and three-backend repository tests |
| REQ-REG-B07 | RegistrationService, repository status update | Service, route, and capacity-release tests |
| REQ-REG-B08 | RegistrationService, EventClient, confirmed count | Stats unit/route/integration tests |
| REQ-REG-E01–E08 | Routes and error handlers | Flask contract tests |
| REQ-REG-ERR01 | Domain errors and handlers | Error contract assertions |
| REQ-REG-N01 | Config, clients, entry point | Configuration/client tests |
| REQ-REG-N02 | Repository interface and adapters | Parameterized backend tests |
| REQ-REG-N03 | Complete test suite | Coverage and traceability report |
