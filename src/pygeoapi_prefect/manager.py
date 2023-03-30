"""pygeoapi process manager based on Prefect."""

import logging
from pathlib import Path
from typing import Any

from prefect import flow
from pygeoapi.process.base import BaseProcessor
from pygeoapi.process.manager.base import BaseManager
from pygeoapi.util import JobStatus

from .process.base import BasePrefectProcessor

LOGGER = logging.getLogger(__name__)


class PrefectManager(BaseManager):
    is_async: bool = True
    name: str
    connection: str
    output_dir: Path | None

    def __init__(self, manager_def: dict[str, str]):
        super().__init__(manager_def)

    def get_jobs(self, status: JobStatus = None) -> list[dict]:
        """Get a list of jobs, optionally filtered by status."""
        return []

    def get_job(self, job_id: str) -> dict | None:
        """Get a job."""
        return None

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
        LOGGER.debug(f"inside manager.execute_process - locals: {locals()}")
        # set initial status
        # add job (if needed)
        # request execution

        match p:
            case BasePrefectProcessor():
                LOGGER.warning("This is a BasePrefectProcessor subclass")
                media_type, outputs = p.process_flow(p.process_metadata, **data_dict)
                status = JobStatus.successful
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
