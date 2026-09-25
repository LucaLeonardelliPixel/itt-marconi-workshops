# event-service — Design

**Service:** event-service  
**Requirements:** `.kiro/specs/event-service/requirements.md`  
**Contract:** `contracts/openapi/event-service.yaml`  
**Repository standards:** `.kiro/steering/structure.md`, `.kiro/steering/platform-standards.md`

---

## 1. Design Goals

The event-service will provide a contract-compliant Flask API for TechConf events while keeping HTTP transport, business rules, persistence, and user-service communication independent. The design must satisfy these properties:

1. Every HTTP response matches `contracts/openapi/event-service.yaml`.
2. Business rules REQ-EVT-B01 through REQ-EVT-B06 live in the service layer, not routes or repositories.
3. `memory`, `json`, and `sqlite` persistence are interchangeable through one `EventRepository` interface.
4. User validation is isolated behind a `UserRepository` outbound port so unit tests do not perform network calls.
5. Runtime configuration is centralized and no inter-service URL is hard-coded.
6. The service runs with `python -m app` and binds to the `PORT` environment variable.

---

## 2. Architecture

### 2.1 Layer diagram

```text
HTTP request
    │
    ▼
Flask routes and error handlers
    │ plain dictionaries / domain exceptions
    ▼
EventService business logic
    ├─────────────────────────────┐
    ▼                             ▼
EventRepository port          UserRepository port
    │                             │
    ├─ Memory adapter             └─ HTTP user-service adapter
    ├─ JSON adapter                     │
    └─ SQLite adapter                   ▼
                                  user-service
```

Dependencies point inward toward abstractions:

- Routes depend on `EventService`.
- `EventService` depends on `EventRepository` and `UserRepository` interfaces.
- Persistence and HTTP adapters implement those interfaces.
- Domain logic imports neither Flask nor `requests` nor a concrete persistence adapter.

### 2.2 Component responsibilities

| Component | Responsibility | Must not do |
|---|---|---|
| `config.py` | Read and validate runtime environment configuration | Apply business rules |
| Event routes | Parse HTTP input, invoke service methods, create status/body/headers | Access persistence or call user-service directly |
| Error handlers | Convert domain exceptions into standard error envelopes | Infer business outcomes |
| `EventService` | Validate event fields, organizer, dates, transitions, filters, and pagination | Import Flask or perform raw filesystem/SQL operations |
| `EventRepository` | Define storage operations used by business logic | Validate organizer role or lifecycle transitions |
| Persistence adapters | Store and retrieve complete event dictionaries | Make outbound HTTP calls |
| `UserRepository` | Define the read-only organizer lookup port | Expose `requests.Response` objects |
| HTTP user adapter | Call user-service and translate upstream outcomes into domain exceptions | Persist event data |

---

## 3. Repository and Module Structure

```text
services/event-service/
├── app/
│   ├── __init__.py                 # create_app() and dependency wiring
│   ├── __main__.py                 # python -m app; PORT binding
│   ├── config.py                   # environment settings
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── health.py               # GET /health
│   │   └── events.py               # /api/v1/events routes
│   ├── services/
│   │   ├── __init__.py
│   │   ├── exceptions.py           # typed domain/application exceptions
│   │   └── event_service.py        # all REQ-EVT-B* logic
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── event_repository.py     # EventRepository interface
│   │   ├── memory.py               # in-process adapter
│   │   ├── json_repo.py            # JSON file adapter
│   │   └── sqlite_repo.py          # sqlite3 adapter
│   └── clients/
│       ├── __init__.py
│       ├── user_repository.py      # UserRepository outbound interface
│       └── http_user_repository.py # requests-based implementation
├── tests/
│   ├── unit/
│   │   ├── conftest.py
│   │   ├── test_event_repository.py
│   │   ├── test_event_service.py
│   │   ├── test_http_user_repository.py
│   │   └── test_routes_events.py
│   └── integration/
│       ├── conftest.py
│       └── test_user_dependency.py
├── requirements.txt
├── requirements-test.txt
└── pytest.ini
```

The implementation remains fully contained in `services/event-service`. It must never import application modules from `services/user-service`; communication occurs only over HTTP through the `UserRepository` abstraction.

---

## 4. Runtime Configuration and Dependency Wiring

### 4.1 Configuration values

`app/config.py` is the only module that reads environment variables.

| Setting | Environment variable | Default |
|---|---|---|
| Listening port | `PORT` | `5002` |
| user-service base URL | `USER_SERVICE_URL` | `http://localhost:5001` |
| Storage adapter | `STORAGE_BACKEND` | `memory` |
| File storage directory | `DATA_DIR` | `./data` |
| HTTP timeout | Internal constant | 2 seconds |

The user-service URL is normalized by removing a trailing slash before resource paths are appended. Acceptance URLs such as `http://127.0.0.1:15001` therefore work without code changes.

### 4.2 Application factory

`create_app` is responsible only for composition:

1. Load validated configuration.
2. Select or accept an injected `EventRepository`.
3. Build or accept an injected `UserRepository`.
4. Construct `EventService(event_repository, user_repository)`.
5. Register event and health blueprints.
6. Register domain exception handlers.

Tests can inject fake repositories directly. Production/development startup uses the configured adapters.

### 4.3 Process entry point

`app/__main__.py` creates the application and binds Flask to `0.0.0.0` on configured `PORT`. The manifest command remains `python -m app` with working directory `services/event-service`.

---

## 5. Domain Model

### 5.1 Stored event record

The repository stores one dictionary per event with these fields:

| Field | Stored representation |
|---|---|
| `id` | Canonical UUID v4 string |
| `title` | String |
| `description` | String or null |
| `organizer_id` | Canonical UUID string |
| `venue` | String |
| `city` | String |
| `start_date` | `YYYY-MM-DD` string |
| `end_date` | `YYYY-MM-DD` string |
| `capacity` | Integer |
| `price` | JSON-compatible number rounded/formatted consistently to two decimal semantics |
| `status` | `draft`, `published`, or `cancelled` |
| `created_at` | ISO 8601 UTC string ending in `Z` |
| `updated_at` | ISO 8601 UTC string ending in `Z` |

The service layer constructs and validates complete records before persistence. Repositories do not add defaults or mutate business fields.

### 5.2 Immutability

- `id` and `created_at` are generated once and preserved by PUT/PATCH.
- Client bodies containing `id`, `created_at`, or `updated_at` are rejected as unknown/read-only properties.
- `updated_at` is refreshed only after a successful update validation path.
- Failed organizer checks, field validation, or transition checks leave stored records unchanged.

---

## 6. Ports and Adapters

### 6.1 EventRepository interface

The event storage port exposes operations equivalent to:

| Operation | Input | Output |
|---|---|---|
| Insert | Complete event dictionary | Stored event dictionary |
| Find by ID | Event ID | Event dictionary or none |
| Find all | Optional `status` and `city` filters | Ordered list of event dictionaries |
| Replace/update | Event ID and complete event dictionary | Updated dictionary or none |
| Delete | Event ID | Boolean indicating whether a record existed |

Adapters return copies/plain dictionaries so callers cannot mutate persistence state accidentally. Filtering occurs before pagination; the service calculates `total` and page slices.

### 6.2 Memory adapter

- Uses an in-process dictionary keyed by event ID.
- Is the default backend.
- Preserves insertion order for deterministic list tests.
- Returns defensive copies.
- Does not persist across process restarts.

### 6.3 JSON adapter

- Uses `$DATA_DIR/events.json`.
- Creates the parent directory and initializes an empty collection when necessary.
- Uses only Python standard-library `json` and file APIs.
- Protects read-modify-write operations with a lock.
- Writes through a temporary file followed by replacement to reduce partial-write risk.
- Produces the same observable behavior as the memory adapter.

### 6.4 SQLite adapter

- Uses `$DATA_DIR/events.db` and Python standard-library `sqlite3` only.
- Creates an `events` table on initialization if absent.
- Uses `id TEXT PRIMARY KEY` and columns matching all event fields.
- Uses parameterized SQL for every query.
- Converts rows to the same plain dictionary shape as other adapters.
- Opens scoped connections and commits writes atomically.

### 6.5 UserRepository outbound port

The read-only user port exposes one operation: retrieve a user by UUID for organizer validation. It returns a plain user dictionary on success and raises typed application exceptions for missing or unavailable dependencies.

The HTTP implementation:

1. Calls `{USER_SERVICE_URL}/api/v1/users/{id}` with timeout 2 seconds.
2. Returns parsed JSON for a valid `200` user response.
3. Translates upstream `404` to `ReferenceNotFoundError`.
4. Translates timeout, connection errors, malformed upstream responses, and upstream `5xx` to `DependencyUnavailableError`.
5. Never leaks `requests` exceptions or response objects into `EventService`.

Unexpected upstream `4xx` responses are treated as dependency failures because event-service cannot safely validate the organizer.

---

## 7. EventService Design

### 7.1 Public operations

| Service operation | Responsibilities |
|---|---|
| Create | Validate create schema, dates, capacity/price, organizer existence/role; generate metadata; persist |
| List | Validate pagination and filters; fetch filtered records; return `EventPage` |
| Get | Find by ID or raise not found |
| Replace | Verify target exists; validate full replacement and resulting transition; validate organizer; preserve immutable fields; persist |
| Partial update | Verify target exists; reject empty/unknown body; merge; validate resulting event and relevant organizer; persist |
| Delete | Delete existing record or raise not found |

### 7.2 Validation order

Validation is deterministic and avoids unnecessary network calls:

1. Confirm request is a JSON object at the HTTP boundary.
2. Reject missing required, read-only, or unknown fields.
3. Validate primitive types, lengths, enum values, UUID, numeric bounds, and real ISO dates.
4. Load the current event for PUT/PATCH and return 404 before external calls when it does not exist.
5. Build the resulting complete event state.
6. Validate `end_date >= start_date`.
7. Validate status transition for updates.
8. Validate organizer through `UserRepository` when required.
9. Generate/update timestamps and persist.

This order ensures invalid local data does not trigger outbound calls and no partial write occurs.

### 7.3 Organizer validation

Organizer validation applies to:

- Every create operation.
- Every full replacement.
- Partial updates only when `organizer_id` changes.

A successful user lookup is followed by an exact role check. Any role other than `organizer` raises `InvalidOrganizerError`.

### 7.4 Status transitions

Allowed transitions are represented as a fixed domain table:

| Current | Allowed targets |
|---|---|
| `draft` | `draft`, `published`, `cancelled` |
| `published` | `published`, `cancelled` |
| `cancelled` | `cancelled` |

Self-transitions allow idempotent PUT/PATCH operations. Initial status defaults to `draft` when omitted. No repository adapter enforces transitions; this remains exclusively in `EventService`.

### 7.5 Pagination and filters

- Default page is 1; default page size is 20; maximum is 100.
- Query strings are converted to integers by the route and validated by the service.
- Supported filters are `status` and `city` only.
- Filters are combined with logical AND.
- `total` is calculated after filtering and before slicing.
- An out-of-range page returns an empty `items` array with the original matching `total`.

---

## 8. HTTP API Design

### 8.1 Route mapping

| Method | Path | Service operation | Success |
|---|---|---|---:|
| POST | `/api/v1/events` | Create | 201 + `Location` |
| GET | `/api/v1/events` | List | 200 |
| GET | `/api/v1/events/{id}` | Get | 200 |
| PUT | `/api/v1/events/{id}` | Replace | 200 |
| PATCH | `/api/v1/events/{id}` | Partial update | 200 |
| DELETE | `/api/v1/events/{id}` | Delete | 204, empty body |
| GET | `/health` | Local health | 200 |

### 8.2 Request handling

- POST, PUT, and PATCH require JSON object bodies.
- Syntactically malformed JSON raises `MalformedJsonError` and produces 400.
- Valid JSON of the wrong top-level type produces 422 `VALIDATION_ERROR`.
- Routes pass plain dictionaries and parsed query values to `EventService`.
- Routes do not validate organizer role or status transitions.

### 8.3 Response projection

Responses are projected through explicit field allowlists to prevent adapter metadata or accidental properties from violating `additionalProperties: false`.

POST sets `Location` to the relative resource path `/api/v1/events/{id}`. DELETE returns no JSON body.

---

## 9. Error Handling

### 9.1 Domain exceptions

| Exception | Status | Error code | Trigger |
|---|---:|---|---|
| `MalformedJsonError` | 400 | `MALFORMED_JSON` | Unparseable JSON |
| `NotFoundError` | 404 | `NOT_FOUND` | Local event absent |
| `ValidationError` | 422 | `VALIDATION_ERROR` | Field, date, filter, or pagination invalid |
| `ReferenceNotFoundError` | 422 | `REFERENCE_NOT_FOUND` | Organizer absent in user-service |
| `InvalidOrganizerError` | 422 | `INVALID_ORGANIZER` | Referenced user lacks organizer role |
| `InvalidStatusTransitionError` | 422 | `INVALID_STATUS_TRANSITION` | Forbidden lifecycle transition |
| `DependencyUnavailableError` | 503 | `DEPENDENCY_UNAVAILABLE` | user-service unavailable/unusable |

Every exception contains a stable code, human-readable message, and JSON-object details. Central Flask handlers map each exception to the standard error envelope; route functions do not duplicate mappings.

### 9.2 Error precedence

- A missing local event on GET/PUT/PATCH/DELETE produces 404.
- Locally invalid request data produces 422 without calling user-service.
- A user-service 404 produces 422 `REFERENCE_NOT_FOUND`.
- A valid user with the wrong role produces 422 `INVALID_ORGANIZER`.
- An unavailable user-service produces 503 `DEPENDENCY_UNAVAILABLE`.

---

## 10. Contract Alignment

| OpenAPI element | Design enforcement |
|---|---|
| `EventCreate` | Full-body validator for POST and PUT |
| `EventUpdate` | Non-empty partial-body validator for PATCH |
| `Event` | Explicit response projection with all required fields |
| `EventPage` | Service-generated pagination envelope |
| `Health` | Dedicated health blueprint |
| `Error` | Central exception handlers |
| `Location` | Set by successful POST route |
| Query constraints | Route parsing plus service validation |
| `additionalProperties: false` | Request key validation and response allowlists |

No contract or acceptance-test file will be modified. Contract assertions import the existing helper from `contracts/validator.py` by configuring the test import path, not by copying it.

---

## 11. Testing Strategy

### 11.1 Unit tests

**Repository contract tests** run identically against memory, JSON, and SQLite adapters. File adapters use pytest `tmp_path`. Tests cover insertion, retrieval, replacement, deletion, filters, empty results, persistence/reload, defensive copies, and adapter parity.

**EventService tests** inject an in-memory event repository and a fake `UserRepository`. Tests trace every requirement, including:

- Field boundaries for all event properties.
- UUID/date validation and date ordering.
- Organizer found, missing, wrong role, and dependency unavailable.
- All allowed and forbidden lifecycle transitions.
- Creation defaults and immutable metadata.
- Combined filters and pagination boundaries.
- No write on failed validation.

**HTTP user adapter tests** use `responses` to mock user-service and verify URL composition, two-second timeout, 200/404/5xx mapping, connection errors, and malformed upstream payloads.

**Route tests** use Flask's test client and validate successful and error responses against `assert_matches_contract` for every endpoint and declared response family.

### 11.2 Custom integration tests

Real user-service and event-service processes are started on dynamically selected free ports and shut down reliably in fixture cleanup. Tests cover:

1. Valid organizer: create event returns 201.
2. Missing organizer: create event returns 422 `REFERENCE_NOT_FOUND`.
3. user-service offline: event-service returns 503 `DEPENDENCY_UNAVAILABLE`.

The tests inject `PORT`, `USER_SERVICE_URL`, `STORAGE_BACKEND=memory`, and an isolated `DATA_DIR` through process environments.

### 11.3 Acceptance and coverage

- Targeted service tests: run unit and custom integration tests for event-service.
- Acceptance validation: `pytest tests/integration -k event -v` from repository root after implementation.
- Coverage: `pytest --cov=app --cov-report=term-missing`, with at least 80% line coverage.
- Each test includes a `REQ-EVT-*` ID in its marker, name, or docstring.

---

## 12. Requirement Traceability

| Requirements | Primary component | Verification |
|---|---|---|
| REQ-EVT-B01, B02, B05 | `EventService`, `UserRepository`, HTTP user adapter | Service unit, adapter unit, custom integration |
| REQ-EVT-B03, B04 | `EventService` | Service and route tests |
| REQ-EVT-B06 | `EventService`, event repositories | Service and repository tests |
| REQ-EVT-E01–E07 | Routes, service, error handlers | Flask route contract tests |
| REQ-EVT-ERR01 | Error handlers | Contract assertions for errors |
| REQ-EVT-N01 | Config and entry point | Configuration/startup tests |
| REQ-EVT-N02 | Repository port and three adapters | Parameterized repository tests |
| REQ-EVT-N03 | All test layers | Coverage report and integration tests |

---

## 13. Key Decisions

| Decision | Reason |
|---|---|
| `UserRepository` is an outbound read port, not shared code from user-service | Prevents cross-service imports and isolates HTTP |
| Three separate event persistence adapters | Meets backend requirement without leaking persistence into business logic |
| Organizer validation precedes persistence | Guarantees failed dependencies cannot leave partial events |
| PUT/PATCH load the event before calling user-service | Preserves local 404 semantics and avoids needless calls |
| Status self-transition is allowed | Supports idempotent replacement/update while forbidding lifecycle reversal |
| Explicit response allowlists | Enforces OpenAPI `additionalProperties: false` |
| No common runtime library across services | Keeps service deployment independent in the exam monorepo |
