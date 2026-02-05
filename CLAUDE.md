# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

pygeoapi-prefect is a process/job manager for PyGeoAPI that uses Prefect for workflow orchestration. It enables running geospatial processes as Prefect flow runs, implementing the OGC API - Processes specification.

## Development Commands

```bash
# Install dependencies (includes dev group by default)
uv sync

# Run pre-commit checks (ruff, black, mypy)
uv run pre-commit run --all-files

# Run tests
uv run pytest tests/

# Build documentation
uv run mkdocs build
```

## Running Locally

```bash
# Start Prefect server (terminal 1)
uv run prefect server start

# Configure and start agent (terminal 2)
uv run prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api
uv run prefect agent start --work-queue pygeoapi

# Start PyGeoAPI (terminal 3)
PYGEOAPI_CONFIG=example-config.yml PYGEOAPI_OPENAPI=example-openapi.yml uv run pygeoapi serve

# Deploy a process flow
uv run pygeoapi-prefect deploy-process hi-prefect-world --pygeoapi-config example-config.yml

# Regenerate OpenAPI spec after config changes
uv run pygeoapi openapi generate example-config.yml > example-openapi.yml
```

## Architecture

### Core Components

- **PrefectManager** (`src/pygeoapi_prefect/manager.py`): Core orchestration engine that maps PyGeoAPI jobs to Prefect flow runs. Uses flow run `name` as job_id with `pygeoapi_job_` prefix.

- **BasePrefectProcessor** (`src/pygeoapi_prefect/process/base.py`): Abstract base class for Prefect-enabled processes. Requires implementations to define `process_description` and `process_flow`.

- **Schemas** (`src/pygeoapi_prefect/schemas.py`): Pydantic models implementing OGC API - Processes specification.

- **CLI** (`src/pygeoapi_prefect/cli.py`): Click-based commands registered as pygeoapi subcommand (`pygeoapi-prefect`).

### Execution Flow

1. Standard pygeoapi processes: PrefectManager wraps processor in a Prefect flow on-the-fly
2. Custom Prefect processes (BasePrefectProcessor): Uses `run_deployment()` for deployed flows or runs locally if no deployment

### Flow Function Signature

Custom Prefect processors must implement a flow function with this signature:
```python
@flow(persist_result=True, ...)
def process_flow(
    job_id: str,
    result_storage_block: str | None,
    process_description: schemas.ProcessDescription,
    execution_request: schemas.ExecuteRequest
) -> schemas.JobStatusInfoInternal:
```

## Technical Constraints

- Uses Pydantic v1.x (1.10.7)
- Click pinned to 8.0.0 for pygeoapi compatibility
- Requires local pygeoapi installation (path dependency configured in `[tool.uv.sources]`)
- Uses anyio for async Prefect API communication

## Configuration

Process configuration in PyGeoAPI config files (see `example-config.yml`):
- `server.manager.name`: Set to `pygeoapi_prefect.manager.PrefectManager`
- `resources.{name}.processor.prefect`: Configure deployment settings and result storage blocks
