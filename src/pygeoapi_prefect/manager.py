"""pygeoapi process manager based on Prefect."""

import logging
import uuid
from pathlib import Path
from typing import Any

import anyio
from prefect import flow
from prefect.client.orchestration import get_client
from prefect.client.schemas import FlowRun
from prefect.server.schemas import filters
from prefect.server.schemas.core import Flow
from prefect.server.schemas.states import StateType
from pygeoapi.process.base import BaseProcessor
from pygeoapi.process.manager.base import BaseManager
from pygeoapi.util import JobStatus

from .process.base import BasePrefectProcessor
from . import schemas

LOGGER = logging.getLogger(__name__)


class PrefectManager(BaseManager):
    is_async: bool
    name: str
    connection: str
    output_dir: Path | None

    prefect_state_map = {
        StateType.SCHEDULED: JobStatus.accepted,
        StateType.PENDING: JobStatus.accepted,
        StateType.RUNNING: JobStatus.running,
        StateType.COMPLETED: JobStatus.successful,
        StateType.FAILED: JobStatus.failed,
        StateType.CANCELLED: JobStatus.dismissed,
        StateType.CRASHED: JobStatus.failed,
        StateType.PAUSED: JobStatus.accepted,
        StateType.CANCELLING: JobStatus.dismissed,
    }

    def __init__(self, manager_def: dict[str, str]):
        super().__init__(manager_def)
        self.is_async = True

    def get_jobs(self, status: JobStatus = None) -> list[dict]:
        """Get a list of jobs, optionally filtered by status."""
        prefect_state = None
        if status is not None:
            for k, v in self.prefect_state_map.items():
                if status == v:
                    prefect_state = k
                    break
        flow_runs = anyio.run(
            _get_prefect_flow_runs, prefect_state, ["pygeoapi"])
        seen_flows = {}
        jobs = []
        for flow_run in flow_runs:
            if flow_run.flow_id not in seen_flows:
                flow = anyio.run(_get_prefect_flow, flow_run.flow_id)
                seen_flows[flow_run.flow_id] = flow
            job_status = self._flow_run_to_job_status(
                flow_run, seen_flows[flow_run.flow_id])
            jobs.append(job_status.dict(by_alias=True))
        return jobs

    def get_job(self, job_id: str) -> dict | None:
        """Get a job."""
        flow_run, flow = anyio.run(_get_prefect_flow_run, uuid.UUID(job_id))
        job_status_info = self._flow_run_to_job_status(flow_run, flow)
        return job_status_info.dict(by_alias=True)

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

    def add_job(self, job_metadata: dict) -> str:
        """Add a job.

        This method is part of the ``pygeoapi.BaseManager`` API. However, in
        the context of prefect we do not need it.
        """
        raise NotImplementedError

    def update_job(self, job_id: str, update_dict: dict) -> bool:
        """Update an existing job.

        This method is part of the ``pygeoapi.BaseManager`` API. However, in
        the context of prefect we do not need it.
        """
        raise NotImplementedError

    def _flow_run_to_job_status(
            self,
            flow_run: FlowRun,
            prefect_flow: Flow
    ) -> schemas.JobStatusInfo:
        return schemas.JobStatusInfo(
            jobID=str(flow_run.id),
            status=self.prefect_state_map[flow_run.state_type],
            processID=prefect_flow.name,
            created=flow_run.created,
            started=flow_run.start_time,
            finished=flow_run.end_time,
        )


async def _get_prefect_flow_runs(
        state: StateType | None = None,
        tags: list[str] | None = None
) -> list[FlowRun]:
    if state is not None:
        state_filter = filters.FlowRunFilterState(
            type=filters.FlowRunFilterStateType(any_=[state]))
    else:
        state_filter = None
    if tags is not None:
        tags_filter = filters.FlowRunFilterTags(all_=tags)
    else:
        tags_filter = None
    async with get_client() as client:
        response = await client.read_flow_runs(
            flow_run_filter=filters.FlowRunFilter(
                tags=tags_filter,
                state=state_filter
            )
        )
    return response


async def _get_prefect_flow_run(
        flow_run_id: uuid.UUID) -> tuple[FlowRun, Flow]:
    async with get_client() as client:
        flow_run = await client.read_flow_run(flow_run_id)
        prefect_flow = await client.read_flow(flow_run.flow_id)
        return flow_run, prefect_flow


async def _get_prefect_flow(flow_id: uuid.UUID) -> Flow:
    async with get_client() as client:
        return await client.read_flow(flow_id)
