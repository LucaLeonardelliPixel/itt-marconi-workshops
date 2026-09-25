# TechConf — Platform Standards

> **Source of truth:** §4 of `Exam.MD`. These rules apply to ALL services without exception.
> Violation of the rules marked ⚠️ carries an exam point penalty.

---

## Service Startup

- The acceptance suite reads `services.yaml` (repo root) to launch each service.
- Each service **MUST** listen on the port given by the `PORT` environment variable.  
  ⚠️ Never hard-code a port number — use `int(os.environ.get("PORT", <default>))`.
- Default development ports: 5001–5005. Acceptance ports: 15001–15005.

---

## Environment Variables

Every service reads these at startup (never hard-coded):

| Variable | Purpose | Default |
|---|---|---|
| `PORT` | TCP port to bind | service-specific (5001–5005) |
| `USER_SERVICE_URL` | Base URL of user-service | `http://localhost:5001` |
| `EVENT_SERVICE_URL` | Base URL of event-service | `http://localhost:5002` |
| `REGISTRATION_SERVICE_URL` | Base URL of registration-service | `http://localhost:5003` |
| `FEEDBACK_SERVICE_URL` | Base URL of feedback-service | `http://localhost:5004` |
| `NOTIFICATION_SERVICE_URL` | Base URL of notification-service | `http://localhost:5005` |
| `STORAGE_BACKEND` | `memory` \| `json` \| `sqlite` | `memory` |
| `DATA_DIR` | Directory for json/sqlite files | `./data` |

⚠️ **Never hard-code a `*_SERVICE_URL`** — always read from the environment variable.  
⚠️ **Never import or install an external DBMS library** — only `json`, `sqlite3` (stdlib).

---

## URL Structure

- All resource endpoints: `/api/v1/<resource>` (plural, snake_case).
- Examples: `/api/v1/users`, `/api/v1/events`, `/api/v1/registrations`.

---

## Data Format

- All request and response bodies: `Content-Type: application/json`.
- All field names: `snake_case`.
- Resource IDs: UUID v4, **generated server-side**, never accepted from client input.
- Timestamps: ISO 8601 UTC, e.g. `"2026-10-15T09:30:00Z"`. Every resource has `created_at` and `updated_at` (read-only).
- Dates: `YYYY-MM-DD` (e.g. `"2026-10-15"`).
- Monetary amounts: `number` with 2 decimal places (e.g. `149.00`), currency EUR implicit.

---

## Pagination

All list endpoints accept `?page=1&page_size=20` (max `page_size` = 100).

Response shape (mandatory, `additionalProperties: false`):
```json
{
  "items": [...],
  "page": 1,
  "page_size": 20,
  "total": 57
}
```

---

## Error Envelope

All error responses (4xx, 5xx) use this shape (mandatory, `additionalProperties: false`):
```json
{
  "error": {
    "code": "UPPER_SNAKE_CASE",
    "message": "Human-readable explanation",
    "details": {}
  }
}
```

The `details` object is optional but must be present as `{}` if no extra info is provided.

---

## HTTP Status Codes

| Code | When |
|---|---|
| `201 Created` | Resource created — **must** include `Location: /api/v1/<resource>/<id>` header |
| `200 OK` | Read or update |
| `204 No Content` | Delete (no body) |
| `400 Bad Request` | Malformed JSON body (`{"error": {"code": "MALFORMED_JSON", ...}}`) |
| `404 Not Found` | Resource not found (`NOT_FOUND`) |
| `405 Method Not Allowed` | Method explicitly forbidden by contract |
| `409 Conflict` | Business conflict (e.g. `EMAIL_ALREADY_EXISTS`, `ALREADY_REGISTERED`, `EVENT_FULL`) |
| `422 Unprocessable Entity` | Validation error or broken reference (`VALIDATION_ERROR`, `REFERENCE_NOT_FOUND`, `INVALID_*`) |
| `503 Service Unavailable` | Upstream service unreachable (`DEPENDENCY_UNAVAILABLE`) |

---

## Inter-Service Calls

- **Timeout:** 2 seconds (`requests.get(..., timeout=2)`).
- **404 from upstream** → respond `422 REFERENCE_NOT_FOUND`.
- **Timeout / connection refused / 5xx from upstream** → respond `503 DEPENDENCY_UNAVAILABLE`.
- URL read from `*_SERVICE_URL` env var; fallback to `http://localhost:<port>`.

---

## Health Endpoint

Every service exposes:

```
GET /health  →  200
```

Response body (mandatory shape, `additionalProperties: false`):
```json
{
  "status": "ok",
  "service": "<service-name>"
}
```

Where `<service-name>` matches the service's canonical name (e.g. `"user-service"`, `"event-service"`).

---

## Persistence Rules

- `STORAGE_BACKEND=memory` (default): all data in a Python `dict`; lost on restart.
- `STORAGE_BACKEND=json`: data persisted to `$DATA_DIR/<resource>.json`.
- `STORAGE_BACKEND=sqlite`: data persisted to `$DATA_DIR/<resource>.db`.
- Switching backends must not require any change in business logic.
- `data/` directory is in `.gitignore`.

---

## Spec-Driven Workflow Rules

- Code applicativo **VIETATO** in Vibe mode (solo per bugfix dopo test falliti).
- Workflow obbligatorio: `requirements.md` → `design.md` → `tasks.md` → commit → code.
- Commit message format: `spec(<svc>): requirements` / `feat(<svc>): <task> [T-NN]` / `fix(<svc>): <desc> (closes #N)`.
