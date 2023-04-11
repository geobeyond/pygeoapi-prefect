"""pygeoapi process manager based on Prefect."""

import logging
import uuid
from os import environ
from pathlib import Path
from typing import Any

import anyio
from prefect import flow
from prefect.client.orchestration import get_client
from prefect.server.schemas import filters
from pygeoapi.plugin import load_plugin
from pygeoapi.process.base import BaseProcessor
from pygeoapi.process.manager.base import BaseManager
from pygeoapi.util import (
    JobStatus,
    yaml_load
)

from .process.base import BasePrefectProcessor
from . import schemas

LOGGER = logging.getLogger(__name__)


async def _get_prefect_flow_runs(tags: list[str] | None = None):
    async with get_client() as client:
        response = await client.read_flow_runs(
            flow_run_filter=filters.FlowRunFilter(
                tags=filters.FlowRunFilterTags(all_=tags)
            )
        )
    return response


async def _get_prefect_flow_run(flow_run_id: uuid.UUID):
    async with get_client() as client:
        flow_run = await client.read_flow_run(flow_run_id)
        flow = await client.read_flow(flow_run.flow_id)
        return flow_run, flow


class PrefectManager(BaseManager):
    is_async: bool
    name: str
    connection: str
    output_dir: Path | None

    def __init__(self, manager_def: dict[str, str]):
        super().__init__(manager_def)
        self.is_async = True

    def get_jobs(self, status: JobStatus = None) -> list[dict]:
        """Get a list of jobs, optionally filtered by status."""
        flow_runs = anyio.run(_get_prefect_flow_runs, ["pygeoapi"])
        return [fl.id for fl in flow_runs]

    def get_job(self, job_id: str) -> dict | None:
        """Get a job."""
        flow_run, flow = anyio.run(_get_prefect_flow_run, uuid.UUID(job_id))
        # FIXME: it would be cleaner to be given the relevant process config at initialization time
        pygeoapi_config_path = Path(environ.get("PYGEOAPI_CONFIG"))
        with pygeoapi_config_path.open() as fh:
            pygeoapi_config = yaml_load(fh)
        process_config = pygeoapi_config["resources"][flow.name]["processor"]
        process = load_plugin("process", process_config)
        job = schemas.Job(
            identifier=job_id,
            process_id=flow.name,
            status=None,
            location=None,
            mimetype=process.process_metadata.outputs["result"].schema_.content_media_type,
            job_start_datetime=flow_run.start_time,
            job_end_datetime=flow_run.end_time,
            message=None,
            progress=None,
        )
        return flow_run, flow, process

    def add_job(self, job_metadata: dict) -> str:
        """Add a job."""
        ...

    def update_job(self, job_id: str, update_dict: dict) -> bool:
        """Update an existing job."""
        ...

    def get_job_result(self, job_id: str) -> tuple[str, Any]:
        """Returns the actual output from a completed process."""
        ...

    def delete_job(self, job_id: str) -> bool:
        """Delete a job and associated results/ouptuts."""
        ...

    def execute_process(
            self,
            p: BaseProcessor | BasePrefectProcessor,
            job_id: str,
            data_dict: dict,
            is_async: bool = False
    ) -> tuple[str, dict, JobStatus]:
        """Process execution handler.

        This manager is able to execute two types of processes:

        - Normal pygeoapi processes, i.e. those that derive from
          `pygeoapi.process.base.BaseProcessor`. These are made into prefect flows and
          are run with prefect.
        - Custom prefect-aware processes, which derive from
          `pygeoapi_prefect.processes.base.BasePrefectProcessor`. These are able to take
          full advantage of prefect's features
        """
        LOGGER.warning(f"inside manager.execute_process - locals: {locals()}")
        # set initial status
        # add job (if needed)
        # request execution

        match p:
            case BasePrefectProcessor():
                LOGGER.warning("This is a BasePrefectProcessor subclass")
                media_type, outputs, status = p.execute(
                    job_id, data_dict, process_async=is_async)
            case _:
                LOGGER.warning("This is a standard process")
                executor = flow(
                    p.execute,
                    version=p.metadata.get("version"),
                    flow_run_name=f"pygeoapi-job-{job_id}-{{data[message]}}",
                    validate_parameters=True  # this should be configurable
                    # task_runner=None  # this should be configurable
                    # retries=None  # this should be configurable
                    # retry_delay_seconds=None  # this should be configurable
                    # timeout_seconds=None  # this should be configurable
                )
                media_type, outputs = executor(data_dict)
                status = JobStatus.successful
        return media_type, outputs, status
