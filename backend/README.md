# Backend Overview

This backend is a Flask-based API with Celery integration and Alembic migrations. SQLite is used by default for local development.

## How to run (local dev)

- Create and activate venv (if not using the checked-in `venv`):
  - Windows PowerShell: `python -m venv venv; .\venv\Scripts\Activate.ps1; pip install -r requirements_flask.txt`
- Set environment (optional): copy `env_flask_example` to `.env` and adjust values
- Start Flask app (default http://localhost:5000):
  - `python flask_app.py` or `python main.py`
- Health and routes:
  - Health: `GET /api/v1/health`
  - Route list: `GET /api/v1/routes`

## Key application directories

- `app/` – Main Flask application package
  - `__init__.py` – App factory. Initializes Flask, DB, JWT, CORS, Celery, and registers blueprints (active routes)
  - `config.py` – Flask configuration (SQLite default via `DATABASE_URL`)
  - `extensions.py` – Flask extensions bootstrap (db, jwt, cors, celery)
  - `routes/` – Active Flask blueprints (registered by the app factory)
    - `common_routes.py` – Health check and a route lister (`/api/v1/routes`) to debug 404s
    - `auth.py` – Auth endpoints (`/api/v1/auth/register`, `/api/v1/auth/login`, `/api/v1/auth/me`, etc.). GET `/register` returns usage info
    - `sysadmin_routes.py`, `clientadmin_routes.py`, `schedulemanager_routes.py`, `employee_routes.py` – Role-oriented endpoints
    - `tenant_routes.py`, `user_routes.py`, `department_routes.py`, `schedule_definition_routes.py`, `schedule_permission_routes.py`, `schedule_job_log_routes.py` – ERD-style CRUD endpoints
  - `models/` – Active SQLAlchemy models used by the Flask app
    - `tenant.py`, `user.py`, `department.py`, `schedule_definition.py`, `schedule_permission.py`, `schedule_job_log.py`, `schedule_task.py`
    - `__init__.py` re-exports active models
  - `database/`
    - `connection.py` – SQLAlchemy engine/session factory (used by Alembic and services when needed)
  - `core/`
    - `config.py` – Pydantic settings (for services that prefer settings objects)
    - `security.py` – Security helpers (JWT/config helpers for service code)
  - `utils/` – Helpers (logging, security utilities, DB seed helpers, role checks)

- `services/` – Service layer, Celery tasks and integration helpers
- `alembic/` – Alembic migrations
  - `env.py` – Migration environment bound to the active Flask models
  - `versions/` – Migration scripts (empty until generated)

## Top-level backend files

- `flask_app.py` – Flask entrypoint. Creates app via factory and runs on the configured host/port
- `main.py` – Advanced entrypoint that creates app and optionally seeds data; useful for scripted startup
- `requirements_flask.txt` – Full dependency list for Flask stack
- `requirements.txt` – Minimal/common requirements (keep in sync as needed)
- `alembic.ini` – Alembic configuration (SQLite URL by default; env var `DATABASE_URL` overrides)
- `env_flask_example` – Example environment variables for Flask
- `celery_config.py` – Celery configuration
- `celery_tasks.py` – Celery task definitions (imports/binds to Flask context)
- `celery_worker.py` – Worker bootstrap
- `check_celery.py` – Utility script to validate Celery connectivity
- `start_mock_redis.py` – Starts a mock Redis server for dev/testing scenarios
- `create_tables.py` – Creates tables using the SQLAlchemy Base/engine (Flask models path)
- `create_db_tables.py` – Standalone SQLite table creator and schema printer (no app imports; debug aid)
- `view_db.py` – SQLite inspector; prints tables, schema and sample data
- `migrate_db.py` – One-off migration helper for adding columns to existing SQLite tables
- `database.py` – Minimal DB bootstrap used by legacy modules (prefer `app/extensions.py`)
- `scheduling.db` – Example SQLite database file used in development

## Legacy/alternate stacks (keep for reference; not used by the active app)

- `routes/` – Legacy Flask routes not registered by the app factory. If you hit these endpoints, you’ll likely get 404s
- `models/` – Legacy/alternate SQLAlchemy models used by the legacy `routes/`. Duplicates the tables defined in `app/models/`

Recommendation: use `app/models` and `app/routes` as the single source of truth. If desired, move `backend/models` and `backend/routes` to `_legacy_*` to prevent accidental imports.

### Which models directory is in use?

- Active models (IN USE): `backend/app/models`
  - These are bound to the Flask app via the application factory and `app/extensions.py` `db` instance.
  - All registered blueprints in `backend/app/routes` rely on these models.
  - Alembic is aligned to these models (see `backend/alembic/env.py` importing from `app.models.*`).

- Legacy models (NOT IN USE by the running app): `backend/models`
  - Example: `backend/models/department.py`, `backend/models/user.py`, etc.
  - These were paired with legacy `backend/routes`, which are not registered by the current app.
  - Importing these alongside the active models will cause duplicate-table or redefinition errors.
  - Action: keep for reference, or rename folder to `backend/_legacy_models` to avoid accidental imports.

## Common troubleshooting

- 404 on register
  - Ensure you are calling the Flask app at `http://localhost:5000`
  - `GET /api/v1/routes` should list `/api/v1/auth/register` with methods `GET,POST`
  - Register requires POST. Example:
    - PowerShell: `Invoke-WebRequest -Uri http://localhost:5000/api/v1/auth/register -Method POST -ContentType 'application/json' -Body '{"username":"test","password":"password123","email":"t@e.com","role":"employee"}'`

- Duplicate table/model errors
  - Ensure only `app/models` are imported. Avoid mixing legacy `backend/models` types with active models

- SQLite path
  - Default `DATABASE_URL=sqlite:///smart_scheduling.db` or `scheduling_system.db`. You can use an absolute path: `sqlite:////C:/path/to/db.sqlite`

- Missing dependencies
  - If you get `ModuleNotFoundError: No module named 'bcrypt'` or `'marshmallow'`, run: `pip install -r requirements_flask.txt`
  - All required packages are listed in `requirements_flask.txt`
  - Common missing packages: `bcrypt`, `marshmallow`, `requests`
  - **Fix applied:** Added marshmallow to requirements and made schema imports optional in all route files

- Marshmallow schema errors
  - If you see `TypeError: Field.__init__() got an unexpected keyword argument 'missing'` or `'default'`, your Marshmallow version doesn't support these parameters
  - Fixed in `app/schemas/__init__.py` by replacing `missing=X` with `required=False, allow_none=True` or `required=False`
  - Default values are now handled in the application logic rather than schema definitions

## Migrations workflow (Alembic)

- Generate migration: `alembic revision --autogenerate -m "message"`
- Apply migration: `alembic upgrade head`
- Downgrade: `alembic downgrade -1`

Alembic reads the URL from env var `DATABASE_URL` or `alembic.ini`.

## Simplification checklist (done)

- Single source of truth for models and routes: `app/models` and `app/routes`
- Legacy stacks documented; recommend moving `backend/models` and `backend/routes` to `_legacy_*` if you want to hide them from imports
- SQLite is the default DB; env examples updated; MySQL deps removed
- Alembic configured against Flask models; migration steps documented
- Route lister added at `GET /api/v1/routes` for quick 404 debugging

## Testing & Verification

### Setting Up Test Data

**First time setup - Seed test users:**
```bash
python reset_and_seed_db.py
```

This creates:
- 4 test users (Client_Admin, Client_Admin (legacy), Schedule_Manager, Department_Employee)
- 1 tenant and 1 department
- 1 schedule definition with permissions

**Test Credentials:**
See `TEST_CREDENTIALS.md` for all login credentials.

### Quick Tests
1. **Start the API server:**
   ```bash
   python main.py
   ```
   ⚠️ **Important:** If you get 404 errors, restart the server to pick up route changes!

2. **Verify routes are registered:**
   ```bash
   # In another terminal (while server is running)
   python verify_server.py
   ```
   This will show you which routes are actually registered.

3. **Test endpoints:**
   - Root endpoint: open `http://localhost:5000/` - Shows API information
   - Health: open `http://localhost:5000/api/v1/health`
   - List all routes: open `http://localhost:5000/api/v1/routes`
   
4. **If routes show 404:**
   - **Stop the server** (Ctrl+C)
   - **Restart**: `python main.py`
   - The server must be restarted after any code changes!

### Comprehensive Endpoint Testing
Run the automated test suite to test all endpoints and identify 404 errors:

```bash
# Terminal 1: Start the server
python main.py

# Terminal 2: Run the test suite
python test_all_endpoints.py
```

The test script will:
- Test all public endpoints
- Register/login to get auth token
- Test all protected endpoints
- Generate a report showing which endpoints work and which return 404

### Manual Testing
- Register (POST):
  ```powershell
  Invoke-WebRequest -Uri http://localhost:5000/api/v1/auth/register -Method POST -ContentType 'application/json' -Body '{"username":"test","password":"password123","email":"t@e.com","role":"employee"}'
  ```
- View DB (SQLite): `python view_db.py`

### Endpoint Documentation
See `ENDPOINTS.md` for complete API documentation with all available endpoints, request/response formats, and examples.
