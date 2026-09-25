# Implementation Plan

**Spec:** user-service  
**Design:** `.kiro/specs/user-service/design.md`  
**Requirements:** `.kiro/specs/user-service/requirements.md`  
**Contract:** `contracts/openapi/user-service.yaml`

---

## Overview

This plan implements the `user-service` microservice end-to-end: project scaffolding, domain exceptions, a pluggable repository layer (memory / JSON / SQLite), a `UserService` business-logic layer, Flask HTTP routes with an application factory, and a full unit + integration test suite targeting ≥ 80% line coverage across all three storage backends.

Tasks are ordered so that each layer is stable before the layer above it is built: exceptions → repository interface → concrete adapters → service methods → HTTP layer → tests → coverage gate.

---

## Tasks

- [x] 1. Set up project structure and domain exceptions

  Create the `user-service/` directory tree as specified in the design:

  ```
  user-service/
  ├── app.py
  ├── routes/
  │   └── users.py
  ├── service/
  │   ├── user_service.py
  │   └── exceptions.py
  ├── repository/
  │   ├── base.py
  │   ├── memory.py
  │   ├── json_repo.py
  │   └── sqlite_repo.py
  └── tests/
      ├── conftest.py
      ├── test_routes_users.py
      ├── test_service.py
      └── test_repository.py
  ```

  Populate `service/exceptions.py` with the four domain exception classes (`MalformedJsonError`, `ValidationError`, `EmailConflictError`, `NotFoundError`), each carrying a `code` attribute matching the contract's `UPPER_SNAKE_CASE` codes.

  _Requirements: REQ-USR-E01, REQ-USR-E02, REQ-USR-E03, REQ-USR-E04, REQ-USR-E05, REQ-USR-E06_

---

- [x] 2. Implement the `UserRepository` abstract interface

  In `repository/base.py`, define the `UserRepository` ABC with the six abstract methods: `insert`, `find_by_id`, `find_all`, `update`, `delete`, `email_exists`. All methods receive and return plain `dict` objects.

  _Requirements: REQ-USR-N02, REQ-USR-N03_

---

- [ ] 3. Implement `MemoryRepository`

  In `repository/memory.py`, implement `MemoryRepository(UserRepository)` backed by an in-process `dict[str, dict]`. Implement all six interface methods. This adapter is the default and the test baseline.

  _Requirements: REQ-USR-N02, REQ-USR-N03_

---

- [ ] 4. Implement `JsonRepository`

  In `repository/json_repo.py`, implement `JsonRepository(UserRepository)` that persists to a single JSON file at the path provided at construction. Reads the full file on every read; writes the full file on every write. Protects concurrent writes with a `threading.Lock`. Resolves `DATA_DIR` from the caller (injected path), not read directly from the environment.

  _Requirements: REQ-USR-N02, REQ-USR-N03_

---

- [ ] 5. Implement `Sqlite3Repository`

  In `repository/sqlite_repo.py`, implement `Sqlite3Repository(UserRepository)` using Python's built-in `sqlite3` module. Create the `users` table with `CREATE TABLE IF NOT EXISTS` on first connection. Use parameterised queries for all read/write operations. Column layout mirrors the `User` schema; `id` is the primary key (TEXT).

  _Requirements: REQ-USR-N02, REQ-USR-N03_

---

- [ ] 6. Implement `UserService` — create and email uniqueness

  In `service/user_service.py`, implement `UserService(repo: UserRepository)` with the `create(data)` method:
  - Validate all `UserCreate` fields (required fields, lengths, email format, no extra keys).
  - Normalise email to lowercase/stripped.
  - Enforce email uniqueness via `repo.email_exists`; raise `EmailConflictError` on collision.
  - Generate UUID v4 `id`; set `created_at` and `updated_at` to current UTC.
  - Default `role` to `attendee` if omitted.
  - Delegate to `repo.insert`.

  _Requirements: REQ-USR-B01, REQ-USR-B02, REQ-USR-E01_

---

- [ ] 7. Implement `UserService` — list with filtering and pagination

  Add `list(filters, page, page_size)` to `UserService`:
  - Validate `page ≥ 1` and `1 ≤ page_size ≤ 100`; raise `ValidationError` otherwise.
  - Validate `role` filter value if present; raise `ValidationError` for unknown roles.
  - Delegate to `repo.find_all(filters)`; apply pagination slice.
  - Return a `UserPage` dict with `items`, `page`, `page_size`, and `total` (count of filtered results).

  _Requirements: REQ-USR-B03, REQ-USR-E02_

---

- [ ] 8. Implement `UserService` — get by ID

  Add `get(id)` to `UserService`:
  - Delegate to `repo.find_by_id`; raise `NotFoundError` if the result is `None`.

  _Requirements: REQ-USR-E03_

---

- [ ] 9. Implement `UserService` — replace (PUT)

  Add `replace(id, data)` to `UserService`:
  - Validate all `UserCreate` fields.
  - Normalise email; enforce uniqueness excluding the target user (`exclude_id=id`).
  - Raise `NotFoundError` if `id` is absent.
  - Preserve `id` and `created_at`; update `updated_at`.
  - Delegate to `repo.update`.

  _Requirements: REQ-USR-B01, REQ-USR-B02, REQ-USR-E04_

---

- [ ] 10. Implement `UserService` — partial update (PATCH)

  Add `update(id, data)` to `UserService`:
  - Validate `UserUpdate` fields (at least one present; same field-level rules as `UserCreate`).
  - Normalise email if supplied; enforce uniqueness excluding self.
  - Raise `NotFoundError` if `id` is absent.
  - Merge supplied fields onto existing record; never overwrite `id` or `created_at`; update `updated_at`.
  - Delegate to `repo.patch`.

  _Requirements: REQ-USR-B01, REQ-USR-B02, REQ-USR-E05_

---

- [ ] 11. Implement `UserService` — delete

  Add `delete(id)` to `UserService`:
  - Delegate to `repo.delete`; raise `NotFoundError` if the adapter returns `False` (record absent).

  _Requirements: REQ-USR-E06_

---

- [ ] 12. Implement Flask routes and application factory

  In `routes/users.py`, create a Flask `Blueprint` named `users` with all seven route functions (see design §2.1). Each function:
  - Parses request body / query params.
  - Calls the corresponding `UserService` method.
  - Returns the correct HTTP status code, JSON body, and headers (e.g. `Location` on 201).

  In `app.py`, implement `create_app(repo)`:
  - Instantiates `UserService(repo)`.
  - Registers the `users` blueprint.
  - Registers a `@app.errorhandler` for each domain exception, returning the contract `Error` envelope with the correct status code.
  - Exposes a `_build_repo()` helper that reads `STORAGE_BACKEND` and `DATA_DIR` to select the concrete adapter.
  - Runs on `PORT` env var (default `5001`) when invoked as `__main__`.

  _Requirements: REQ-USR-E01, REQ-USR-E02, REQ-USR-E03, REQ-USR-E04, REQ-USR-E05, REQ-USR-E06, REQ-USR-E07, REQ-USR-N01, REQ-USR-N04_

---

- [ ] 13. Write repository-layer unit tests (`test_repository.py`)

  Create `tests/conftest.py` with a `backend_repo` fixture parameterised over `memory`, `json`, `sqlite` (using `tmp_path` for file-based adapters).

  In `tests/test_repository.py`, write tests parameterised via `backend_repo` that verify each adapter satisfies the `UserRepository` contract identically:
  - `insert` stores and returns the user dict.
  - `find_by_id` returns the correct user or `None`.
  - `find_all` returns all users; filters by `role` and `email` when supplied.
  - `update` replaces mutable fields; preserves `id` and `created_at`.
  - `delete` removes the record; returns `False` for unknown id.
  - `email_exists` returns `True` for a known email, `False` otherwise, and correctly handles `exclude_id`.

  _Requirements: REQ-USR-N02, REQ-USR-N03, REQ-USR-N05_

---

- [ ] 14. Write service-layer unit tests (`test_service.py`)

  In `tests/test_service.py`, write tests that call `UserService` methods directly (no HTTP) using `MemoryRepository`:
  - `create`: happy path returns correct `User` dict; email is normalised; `role` defaults to `attendee`; `id` / `created_at` / `updated_at` are server-generated.
  - `create`: raises `ValidationError` for missing required fields, oversized fields, bad email format, unknown extra fields.
  - `create`: raises `EmailConflictError` on duplicate email (case-insensitive).
  - `list`: defaults `page=1`, `page_size=20`; filters by `role`; filters by `email`; combined filters; `total` reflects filtered count.
  - `list`: raises `ValidationError` for `page < 1`, `page_size > 100`, unknown `role` filter.
  - `get`: returns user for known id; raises `NotFoundError` for unknown id.
  - `replace`: updates mutable fields; preserves `id` / `created_at`; updates `updated_at`; raises `NotFoundError`, `EmailConflictError`, `ValidationError`.
  - `update`: merges partial fields; retains unchanged fields; raises `NotFoundError`, `EmailConflictError`, `ValidationError`; rejects empty body.
  - `delete`: removes user; raises `NotFoundError` for unknown id.

  _Requirements: REQ-USR-B01, REQ-USR-B02, REQ-USR-B03, REQ-USR-E01, REQ-USR-E02, REQ-USR-E03, REQ-USR-E04, REQ-USR-E05, REQ-USR-E06, REQ-USR-N05_

---

- [ ] 15. Write HTTP-layer integration tests (`test_routes_users.py`)

  In `tests/test_routes_users.py`, write tests using the Flask test client, parameterised via `backend_repo`. Every happy-path test calls `assert_matches_contract` from `contracts/validator.py`.

  Minimum test cases per endpoint:

  | Endpoint | Tests |
  |---|---|
  | `POST /api/v1/users` | 201 + `Location` header + contract; 400 malformed JSON; 409 duplicate email; 422 missing required field; 422 extra/unknown field |
  | `GET /api/v1/users` | 200 + contract (default pagination); 200 with `role` filter; 200 with `email` filter; 422 `page < 1`; 422 `page_size > 100`; 422 unknown `role` |
  | `GET /api/v1/users/{id}` | 200 + contract; 404 unknown id |
  | `PUT /api/v1/users/{id}` | 200 + contract; 404 unknown id; 409 duplicate email; 422 missing field |
  | `PATCH /api/v1/users/{id}` | 200 + contract; 404 unknown id; 409 duplicate email; 422 invalid field; 422 empty body |
  | `DELETE /api/v1/users/{id}` | 204 empty body; 404 unknown id |
  | `GET /health` | 200 + contract |

  Error responses (4xx) must also be validated: `assert resp.json["error"]["code"] == "<expected code>"`.

  _Requirements: REQ-USR-E01, REQ-USR-E02, REQ-USR-E03, REQ-USR-E04, REQ-USR-E05, REQ-USR-E06, REQ-USR-E07, REQ-USR-N05, REQ-USR-N06_

---

- [ ] 16. Verify ≥ 80% line coverage across all three backends

  Run the full test suite with coverage enabled across all three storage backends:

  ```bash
  pytest tests/ --cov=. --cov-report=term-missing
  ```

  Confirm that the reported line coverage for the `user-service` package is **≥ 80%** with all three backend variants exercised (memory, json, sqlite). Address any coverage gaps before marking this task complete.

  _Requirements: REQ-USR-N05_

---

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": [1] },
    { "wave": 2, "tasks": [2] },
    { "wave": 3, "tasks": [3, 4, 5] },
    { "wave": 4, "tasks": [6] },
    { "wave": 5, "tasks": [7, 8, 9, 10, 11] },
    { "wave": 6, "tasks": [12] },
    { "wave": 7, "tasks": [13, 14, 15] },
    { "wave": 8, "tasks": [16] }
  ]
}
```

```
Task 1 (scaffold + exceptions)
  └── Task 2 (UserRepository ABC)
        ├── Task 3 (MemoryRepository)
        │     ├── Task 6  (UserService.create)
        │     │     ├── Task 7  (UserService.list)
        │     │     ├── Task 8  (UserService.get)
        │     │     ├── Task 9  (UserService.replace)
        │     │     ├── Task 10 (UserService.update)
        │     │     └── Task 11 (UserService.delete)
        │     │           └── Task 12 (Flask routes + app factory)
        │     │                 ├── Task 13 (repo unit tests)
        │     │                 ├── Task 14 (service unit tests)
        │     │                 └── Task 15 (HTTP integration tests)
        │     │                       └── Task 16 (coverage gate ≥ 80%)
        ├── Task 4 (JsonRepository)   ──┘
        └── Task 5 (Sqlite3Repository) ─┘
```

Tasks 3, 4, and 5 are independent of each other and can be implemented in parallel. Tasks 6–11 each extend `UserService` and can be developed sequentially or in parallel once Tasks 1–3 are complete. Tasks 13–15 require Task 12 to be complete. Task 16 is the final gate and depends on all prior tasks.

---

## Notes

- All three repository adapters (memory, JSON, SQLite) must satisfy the same `UserRepository` interface so the service layer and tests are backend-agnostic.
- File-based adapters (`JsonRepository`, `Sqlite3Repository`) must accept their storage path via constructor injection — never read `DATA_DIR` directly from the environment inside the adapter.
- `UserService` must never import from Flask; HTTP concerns belong exclusively in `routes/users.py` and `app.py`.
- The `repo.patch` method referenced in Task 10 is an additional adapter method beyond the six defined in Task 2; update `base.py` and all three adapters when implementing Task 10.
- Coverage is measured across all three backend parameterisations; a line covered only by the memory-backend tests does not count as covered for JSON or SQLite runs.
- The `contracts/validator.py` `assert_matches_contract` helper must be used in every happy-path HTTP test (Task 15) to catch schema drift early.
