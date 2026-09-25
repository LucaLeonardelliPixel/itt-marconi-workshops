# event-service — Implementation Plan

**Requirements:** `.kiro/specs/event-service/requirements.md`  
**Design:** `.kiro/specs/event-service/design.md`  
**Contract:** `contracts/openapi/event-service.yaml`

---

## Overview

This plan implements event-service in four sequential macro-tasks. Each task is independently reviewable and must be completed atomically. No task may modify `contracts/`, `tests/integration/`, or `CHECKSUMS.sha256`. Application code begins only after this plan has been committed.

## Tasks

- [ ] 1. Project structure, domain exceptions, and UserRepository/EventRepository interface + 3 adapters (memory, json, sqlite).

  Create the service under `services/event-service/` using the structure defined in `design.md`: the `app` package, routes, services, repositories, clients, unit and custom integration test directories, pinned dependency files, pytest configuration, and the `python -m app` entry-point skeleton.

  Define typed domain/application exceptions for malformed JSON, local not-found records, validation failures, missing organizer references, invalid organizer role, invalid status transitions, and unavailable dependencies. Each exception must carry the exact OpenAPI-compatible error code, a human-readable message, and JSON-object details.

  Define `EventRepository` as the persistence port for insert, lookup, filtered listing, update/replace, and deletion. Implement behaviorally equivalent adapters:

  - Memory adapter backed by an in-process dictionary and defensive copies.
  - JSON adapter using only standard-library `json`, locked read-modify-write operations, and `$DATA_DIR/events.json`.
  - SQLite adapter using only standard-library `sqlite3`, parameterized queries, and `$DATA_DIR/events.db`.

  Define `UserRepository` as the read-only outbound organizer lookup port and implement its HTTP adapter with `requests`. Read the base URL from `USER_SERVICE_URL` with fallback `http://localhost:5001`, enforce a two-second timeout, translate user-service 404 to `REFERENCE_NOT_FOUND`, and translate connection failures, timeout, malformed/unusable responses, and 5xx responses to `DEPENDENCY_UNAVAILABLE`. Do not import code from user-service.

  Acceptance conditions:

  - The package imports without application startup side effects.
  - All three event adapters expose identical observable repository behavior.
  - File-backed paths are injected/configured and remain under `DATA_DIR`.
  - No external DBMS, ORM, or hard-coded acceptance URL is introduced.

  _Requirements: REQ-EVT-B01, REQ-EVT-B05, REQ-EVT-N01, REQ-EVT-N02_

---

- [ ] 2. EventService business logic (event creation, capacity, organizer validation).

  Implement `EventService` as pure business/application logic over the injected `EventRepository` and `UserRepository` ports. Cover the complete API behavior, not only creation:

  - Validate POST/PUT/PATCH bodies against the EventCreate/EventUpdate field sets, reject read-only and unknown properties, enforce required fields, types, lengths, UUID format, capacity 1–10000, non-negative price, valid enum values, and real `YYYY-MM-DD` dates.
  - Create server-owned UUID v4 IDs and ISO 8601 UTC `created_at`/`updated_at` values; default omitted status to `draft` and nullable description to `null`.
  - Validate every create/full replacement organizer and changed PATCH organizer through `UserRepository`; require role `organizer` and never persist when validation fails.
  - Enforce `end_date >= start_date` for the resulting complete event.
  - Enforce lifecycle transitions `draft→published`, `draft→cancelled`, and `published→cancelled`, while allowing status self-assignment and rejecting all lifecycle reversals.
  - Implement get, delete, full replacement, and partial update while preserving `id` and `created_at` and refreshing `updated_at` only on success.
  - Implement list filtering by `status` and `city`, logical-AND combination, pagination defaults/bounds, post-filter `total`, and empty out-of-range pages.
  - Ensure local validation and local 404 outcomes occur before unnecessary user-service calls.

  Acceptance conditions:

  - All REQ-EVT-B01 through REQ-EVT-B06 rules are isolated in the service layer.
  - Business logic imports neither Flask nor concrete persistence adapters nor `requests`.
  - Failed operations do not mutate stored event state.
  - Every service result can be serialized directly into the OpenAPI response schemas.

  _Requirements: REQ-EVT-B01, REQ-EVT-B02, REQ-EVT-B03, REQ-EVT-B04, REQ-EVT-B05, REQ-EVT-B06, REQ-EVT-E01, REQ-EVT-E02, REQ-EVT-E03, REQ-EVT-E04, REQ-EVT-E05, REQ-EVT-E06_

---

- [ ] 3. Flask routes, error handlers, and app factory.

  Implement the Flask HTTP layer and runtime composition:

  - Register POST/GET collection routes and GET/PUT/PATCH/DELETE item routes under `/api/v1/events`.
  - Add `GET /health` returning exactly `200 {"status":"ok","service":"event-service"}` without probing user-service.
  - Parse malformed JSON separately from schema-invalid JSON and pass plain values to `EventService`.
  - Return exact success statuses: 201 with `Location` for create, 200 for list/read/update, and empty 204 for delete.
  - Project response dictionaries through contract field allowlists so `additionalProperties: false` is respected.
  - Register centralized handlers that produce the strict `{"error":{"code":"...","message":"...","details":{...}}}` envelope for 400, 404, 422, and 503 cases.
  - Implement `create_app` dependency wiring with optional repository/client injection for tests.
  - Centralize `PORT`, `USER_SERVICE_URL`, `STORAGE_BACKEND`, and `DATA_DIR` reads in configuration; start with `python -m app` and bind to environment `PORT` with default 5002.

  Acceptance conditions:

  - Every route and error status declared by the OpenAPI contract is represented.
  - Event routes contain no persistence logic, organizer-role decisions, or lifecycle rules.
  - Alternate acceptance ports and injected dependency URLs work without source changes.
  - Protected contracts and acceptance tests remain untouched.

  _Requirements: REQ-EVT-E01, REQ-EVT-E02, REQ-EVT-E03, REQ-EVT-E04, REQ-EVT-E05, REQ-EVT-E06, REQ-EVT-E07, REQ-EVT-ERR01, REQ-EVT-N01_

---

- [ ] 4. Unit/Integration tests with contract assertions `assert_matches_contract` and pytest coverage >= 80%.

  Build the complete event-service verification suite:

  - Parameterize repository contract tests over memory, JSON, and SQLite; use `tmp_path` for file-backed adapters and verify parity, filtering, persistence/reload, update, deletion, and isolation.
  - Unit-test `EventService` for all field boundaries, creation defaults, immutable metadata, capacity, date ordering, every allowed/forbidden status transition, pagination, combined filters, local 404s, organizer existence/role, dependency failures, and no-write-on-error behavior.
  - Unit-test the HTTP `UserRepository` adapter with `responses`, including configured URL composition, the two-second timeout, 200, 404, 5xx, connection failure, timeout, and malformed upstream responses.
  - Test Flask endpoints with the test client. Validate at least one response for every endpoint—and representative declared error statuses—with `contracts/validator.py::assert_matches_contract`.
  - Add custom cross-service integration tests that launch real user-service and event-service instances on free ports and verify one valid organizer case, one missing organizer returning 422 `REFERENCE_NOT_FOUND`, and one stopped/unreachable dependency returning 503 `DEPENDENCY_UNAVAILABLE`.
  - Tag or document tests with corresponding `REQ-EVT-*` identifiers.
  - Run targeted tests and produce at least 80% line coverage for the event-service `app` package across all three persistence backends.

  Acceptance conditions:

  - All event-service tests pass without modifying protected files.
  - Each endpoint has an OpenAPI contract assertion.
  - Memory, JSON, and SQLite are all exercised.
  - Cross-service positive, missing-reference, and unavailable-dependency paths pass.
  - Reported event-service application line coverage is at least 80%.

  _Requirements: REQ-EVT-B01, REQ-EVT-B02, REQ-EVT-B03, REQ-EVT-B04, REQ-EVT-B05, REQ-EVT-B06, REQ-EVT-E01, REQ-EVT-E02, REQ-EVT-E03, REQ-EVT-E04, REQ-EVT-E05, REQ-EVT-E06, REQ-EVT-E07, REQ-EVT-ERR01, REQ-EVT-N02, REQ-EVT-N03_

---

## Execution Waves

The macro-tasks execute sequentially because each wave establishes abstractions or behavior needed by the next wave.

```json
{
  "waves": [
    {
      "wave": 1,
      "tasks": [1],
      "depends_on": [],
      "exit_criteria": "Project imports, domain errors and ports exist, and all three event persistence adapters plus the HTTP user adapter satisfy their interfaces."
    },
    {
      "wave": 2,
      "tasks": [2],
      "depends_on": [1],
      "exit_criteria": "EventService implements all event business rules through injected interfaces with no HTTP-framework or concrete-adapter coupling."
    },
    {
      "wave": 3,
      "tasks": [3],
      "depends_on": [2],
      "exit_criteria": "All OpenAPI routes, statuses, headers, error envelopes, health behavior, and environment-driven startup are implemented."
    },
    {
      "wave": 4,
      "tasks": [4],
      "depends_on": [3],
      "exit_criteria": "Unit and custom integration tests pass, every endpoint has contract validation, all backends are tested, and app coverage is at least 80%."
    }
  ]
}
```

## Dependency Graph

```text
Task 1: Structure, ports, adapters
  └── Task 2: EventService business logic
        └── Task 3: Flask HTTP layer and composition
              └── Task 4: Unit, contract, integration, and coverage verification
```

## Implementation Notes

- Complete and commit each macro-task before starting its dependent wave.
- Keep business rules in `EventService`; adapters only translate storage or upstream HTTP behavior.
- Use environment-derived service URLs and a two-second inter-service timeout.
- Use only standard-library `json`/file APIs and `sqlite3` for persistent storage.
- Never edit `contracts/`, `tests/integration/`, or `CHECKSUMS.sha256`.
- A specification defect discovered during implementation requires updating `requirements.md`, then `design.md`, then this plan before code changes.
