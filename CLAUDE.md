# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CaseHUB is a FastAPI-based API and UI automation testing platform. It provides:

- API test case management and execution (HTTP requests, assertions, variables, scripts)
- UI automation via Playwright
- Scheduled jobs via APScheduler
- Test reports and notifications

Backend stack: FastAPI 0.121, SQLAlchemy 2.0, Pydantic 2, Redis, MySQL, APScheduler, Celery (installed but not actively used in current master).

## Common Commands

### Environment Setup

```bash
# Create and activate virtualenv (repo already contains venv/)
python -m venv venv
source venv/bin/activate

# Install dependencies
# Note: the file is named requirment.txt (missing an 'e')
pip install -r requirment.txt
```

### Run the Development Server

```bash
# Using run.py (reload enabled, 4 uvicorn workers)
python run.py
```

> ⚠️ `run.py` references `main:hub`, but the actual FastAPI factory function is `main:caseHub`. If `run.py` fails with "Unable to load application", use `python run.py` only if it has been fixed, or run uvicorn directly:
>
> ```bash
> uvicorn main:caseHub --reload --host 0.0.0.0 --port 5050
> ```

### Run with Gunicorn

```bash
# Directly
gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:5050 main:caseHub

# Or with the provided config file
gunicorn -c gunicorn_conf.py main:caseHub

# Or using restart.sh (also references main:hub and may need correction)
./restart.sh
```

### Run with Docker

```bash
docker-compose up -d
```

The `Dockerfile` and `restart.sh` also currently reference `main:hub` and may need to be changed to `main:caseHub`.

### Initialize Database

```bash
mysql -u root -p autoHub < script/initSQL.sql
```

Default admin account: `admin` / `admin123`.

### Tests and Linting

- There is no `tests/` directory and no project test suite currently.
- There is no linting configuration (`.flake8`, `.pylintrc`, `pyproject.toml`, etc.).
- A basic syntax check can be run with:

```bash
python -m py_compile main.py config.py
```

## Architecture

### Layer Structure

The project follows a layered pattern:

- `app/controller/` — FastAPI routers and request handlers.
- `app/schema/` — Pydantic request/response schemas.
- `app/mapper/` — Data access layer. `app/mapper/__init__.py` contains a large base mapper class with generic CRUD methods (`get_by_id`, `save`, `update_by_id`, `delete_by_id`, `page_query`, etc.).
- `app/model/` — SQLAlchemy ORM models.
- `croe/` — Test execution engines (the directory is intentionally named `croe`, not `core`).
  - `croe/interface/` — API test execution engine.
  - `croe/play/` — UI automation execution engine via Playwright.
- `common/` — Shared clients: `RedisClient`, `MySqlClient`, `OracleClient`, `CatchClient`.
- `utils/` — Utility modules for logging, assertions, file handling, variable transformation, etc.
- `script/` — One-off scripts for DB initialization and method imports.

### Router Registration

Routers are imported in `app/controller/__init__.py` and collected into `RegisterRouterList`, which `main.py` loops over to mount them. If you add a new controller module, import it there and append it to `RegisterRouterList`.

### Execution Flow

1. API/UI tasks are submitted via HTTP controllers.
2. Long-running tasks are queued through `common/worker_pool/` (a Redis-backed async worker pool).
3. `croe/interface/runner.py` and `croe/play/task_runner.py` execute the actual tests.
4. Results are persisted via mappers and reports generated in `utils/report.py`.

### Scheduling

- APScheduler is used for cron/interval-based jobs. Jobs are defined in `app/scheduler/aps/jobs.py`.
- Celery code exists in `app/scheduler/celer9/` but is not actively used on master.

### Configuration

`config.py` defines three config classes:

- `LocalConfig` — local development
- `ProConfig` — production (currently empty, inherits defaults)
- `DockerConfig` — Docker environment

Selection logic at the bottom of `config.py`:

```python
env = os.getenv("ENV", "pro")
if env == "docker":
    Config = DockerConfig
elif env == "dev":
    Config = LocalConfig
else:
    Config = ProConfig
```

Set `ENV=dev` in `.env` or environment to use `LocalConfig`.

Important toggles:

- `WORKER_POOL` — whether WorkPool is enabled.
- `RUN_WORKER_POOL_IN_WEB` — whether the web process also runs the worker pool, or workers run as separate processes.
- `APS` — whether APScheduler is enabled.
- `Record_Proxy` — whether the mitmproxy-based API recorder is enabled.

## Important Gotchas

- `main:hub` vs `main:caseHub`: `run.py`, `Dockerfile`, and `restart.sh` reference `main:hub`, but the actual FastAPI factory function exported by `main.py` is `caseHub`. Fix these references if startup fails.
- `requirment.txt` is misspelled; the correct filename would be `requirements.txt`.
- `gunicorn_conf.py` sets `preload_app = True`. With `uvicorn.workers.UvicornWorker` this can cause issues with async event loops; disable `preload_app` if workers fail to start.
- There is no formal test suite or CI linting; verify changes by running the app locally.
- The `app/mapper/__init__.py` base mapper is central to almost all DB operations. Changes there have wide impact.
- UI automation depends on Playwright browsers. Run `playwright install` if browser binaries are missing.
