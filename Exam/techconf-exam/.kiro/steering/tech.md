# TechConf — Technology Stack

## Runtime

| Component | Choice | Notes |
|---|---|---|
| Language | Python 3.12 | f-strings, `match`, `tomllib`, built-in `uuid`, `datetime` |
| HTTP framework | Flask | Lightweight, no ORM, matches exam requirement |
| HTTP client | requests | For inter-service calls; 2 s timeout mandatory |
| JSON | Standard library `json` | No third-party serializers |

## Persistence

Controlled by the `STORAGE_BACKEND` environment variable. **Only standard library** — no external DBMS.

| Backend | Module | File location |
|---|---|---|
| `memory` (default) | Python `dict` in-process | No files |
| `json` | `json` + file I/O | `$DATA_DIR/<resource>.json` |
| `sqlite` | `sqlite3` | `$DATA_DIR/<resource>.db` |

`DATA_DIR` defaults to `./data` (relative to the service's working directory). The `data/` directory is excluded from git.

The switch between backends must be **transparent to business logic** — only the repository adapter changes.

## Test Dependencies

```
pytest==8.3.5
pytest-cov==6.1.0
responses==0.25.3
PyYAML>=6.0        # used by contracts/validator.py
jsonschema>=4.0    # used by contracts/validator.py
```

## Runtime Dependencies

```
flask>=3.1
requests>=2.32
```

Each service has its own `requirements.txt` in `services/<service-name>/`.

## Entry Point

Every service is started with:
```
python -m app
```
from its working directory (`services/<service-name>/`). The `app/` package contains `__main__.py` which reads `PORT` from the environment and calls `app.run(host="0.0.0.0", port=int(os.environ["PORT"]))`.

## Coverage Target

Unit test coverage ≥ **80%** per service, measured with:
```bash
pytest --cov=app --cov-report=term-missing tests/unit/
```
All three backends (`memory`, `json`, `sqlite`) must be covered using `tmp_path`.

## Contract Validation in Tests

Use `contracts/validator.py::assert_matches_contract(service, method, path, response)` in at least **1 unit test per endpoint** to verify the response shape matches the OpenAPI contract.

## Code Style

- `snake_case` for all field names and Python identifiers.
- Type hints on all function signatures (Python 3.12 union syntax `X | None`).
- No global mutable state outside the repository layer.
- No `print()` in application code; use `app.logger` (Flask) for logging.
