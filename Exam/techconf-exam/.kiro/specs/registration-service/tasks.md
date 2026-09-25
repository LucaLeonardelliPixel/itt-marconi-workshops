# registration-service — Implementation Plan

**Requirements:** `.kiro/specs/registration-service/requirements.md`  
**Design:** `.kiro/specs/registration-service/design.md`  
**Contract:** `contracts/openapi/registration-service.yaml`

## Tasks

- [x] 1. Project setup, domain exceptions, and RegistrationRepository interface + 3 adapters (memory, json, sqlite).

  Create `services/registration-service/` with the `app` package, configuration, routes, services, repositories, dependency clients, tests, pinned requirements, pytest configuration, and `python -m app` entry point. Define typed errors for every required 400/404/405/409/422/503 code. Define `RegistrationRepository` and implement equivalent memory, JSON, and SQLite adapters, including atomic confirmed insertion that checks duplicate `(user_id, event_id)` and event capacity, confirmed counting, filters, status update, and deletion. File adapters use `DATA_DIR`; only standard-library `json`, file APIs, and `sqlite3` are permitted.

  _Requirements: REQ-REG-B04, REQ-REG-B05, REQ-REG-B07, REQ-REG-B08, REQ-REG-ERR01, REQ-REG-N01, REQ-REG-N02_

- [x] 2. RegistrationService business logic (capacity checks, user/event verification, duplicate prevention).

  Implement the business layer over injected repository, user-client, and event-client interfaces. Validate exact POST/PATCH fields and UUIDs; verify user and event references with dynamic environment-derived URLs and two-second timeouts; require a published event; copy event price; create confirmed registrations; map atomic repository outcomes to `ALREADY_REGISTERED` and `EVENT_FULL`; implement list/get/cancel/delete/stats; enforce confirmed-to-cancelled as the only transition; and translate missing references or unavailable dependencies according to operation context. Failed validation must not mutate state.

  _Requirements: REQ-REG-B01, REQ-REG-B02, REQ-REG-B03, REQ-REG-B04, REQ-REG-B05, REQ-REG-B06, REQ-REG-B07, REQ-REG-B08, REQ-REG-B09, REQ-REG-E01, REQ-REG-E02, REQ-REG-E03, REQ-REG-E04, REQ-REG-E05, REQ-REG-E06_

- [x] 3. Flask routes, error handlers, and app factory.

  Implement `/api/v1/registrations` collection/item routes, `/stats`, explicit JSON PUT 405 behavior, and `/health`. Return 201 plus `Location`, 200, empty 204, and strict error envelopes as specified. Centralize `PORT`, `USER_SERVICE_URL`, `EVENT_SERVICE_URL`, `STORAGE_BACKEND`, and `DATA_DIR` configuration. Wire injected/default adapters in `create_app`, project response fields to OpenAPI schemas, and start on environment `PORT` through `python -m app`.

  _Requirements: REQ-REG-E01, REQ-REG-E02, REQ-REG-E03, REQ-REG-E04, REQ-REG-E05, REQ-REG-E06, REQ-REG-E07, REQ-REG-E08, REQ-REG-ERR01, REQ-REG-N01_

- [x] 4. Unit/Integration tests with OpenAPI contract assertions and pytest coverage >= 80%.

  Parameterize repository and Flask `test_client` tests across memory, JSON, and SQLite with `tmp_path`. Unit-test all business rules and mock both HTTP dependencies with `responses`. Validate at least one response for every endpoint using `contracts.validator::assert_matches_contract`, including stats and PUT 405. Add real-HTTP integration scenarios for successful registration, missing user/event references (422), and unavailable dependencies (503). Run coverage against `app` and close all failures/gaps until total line coverage is at least 80%.

  _Requirements: REQ-REG-B01, REQ-REG-B02, REQ-REG-B03, REQ-REG-B04, REQ-REG-B05, REQ-REG-B06, REQ-REG-B07, REQ-REG-B08, REQ-REG-B09, REQ-REG-E01, REQ-REG-E02, REQ-REG-E03, REQ-REG-E04, REQ-REG-E05, REQ-REG-E06, REQ-REG-E07, REQ-REG-E08, REQ-REG-ERR01, REQ-REG-N02, REQ-REG-N03_

## Execution Waves

```json
{
  "waves": [
    {
      "wave": 1,
      "tasks": [1],
      "depends_on": [],
      "exit_criteria": "Project structure, typed errors, dependency ports, and all three atomic persistence adapters are complete."
    },
    {
      "wave": 2,
      "tasks": [2],
      "depends_on": [1],
      "exit_criteria": "RegistrationService implements every registration, capacity, reference, lifecycle, list, and statistics rule."
    },
    {
      "wave": 3,
      "tasks": [3],
      "depends_on": [2],
      "exit_criteria": "All OpenAPI routes, statuses, headers, JSON errors, health behavior, and environment-driven startup are complete."
    },
    {
      "wave": 4,
      "tasks": [4],
      "depends_on": [3],
      "exit_criteria": "All backend, service, client, route, contract, and integration tests pass with app coverage at least 80%."
    }
  ]
}
```

## Dependency Graph

```text
Task 1 → Task 2 → Task 3 → Task 4
```

## Notes

- Complete and commit each wave before starting the next.
- Never modify `contracts/`, `tests/integration/`, or `CHECKSUMS.sha256`.
- Never hard-code acceptance URLs; use `USER_SERVICE_URL` and `EVENT_SERVICE_URL` with localhost development fallbacks.
- Never use an external DBMS or ORM.
- If implementation exposes a specification defect, update requirements, then design, then this plan before changing application behavior.
