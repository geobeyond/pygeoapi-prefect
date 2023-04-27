"""pygeoapi process manager based on Prefect."""

import logging
import uuid
from pathlib import Path
from typing import Any

import anyio
from prefect import flow
from prefect.client.orchestration import get_client
from prefect.client.schemas import FlowRun
from prefect.deployments import run_deployment
from prefect.server.schemas import filters
from prefect.server.schemas.core import Flow
from prefect.server.schemas.states import StateType
from prefect.states import Scheduled
from pygeoapi.models.processes import (
    ExecuteRequest,
    JobStatus,
    JobStatusInfoInternal,
    ProcessExecutionMode,
    RequestedProcessExecutionMode,
)
from pygeoapi.process.base import BaseProcessor
from pygeoapi.process.manager.base import BaseManager

from .process.base import BasePrefectProcessor

logger = logging.getLogger(__name__)


class PrefectManager(BaseManager):
    is_async: bool = True

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

    def get_jobs(
            self,
            type_: list[str] | None = None,
            process_id: list[str] | None = None,
            status: list[JobStatus] | None = None,
            date_time: str | None = None,
            min_duration_seconds: int | None = None,
            max_duration_seconds: int | None = None,
            limit: int | None = 10,
            offset: int | None = 0,
    ) -> tuple[int, list[JobStatusInfoInternal]]:
        """Get a list of jobs, optionally filtered by relevant parameters."""
        if status is not None:
            prefect_states = []
            for k, v in self.prefect_state_map.items():
                if status == v:
                    prefect_states.append(k)
        else:
            prefect_states = [
                StateType.RUNNING,
                StateType.COMPLETED,
                StateType.CRASHED,
                StateType.CANCELLED,
                StateType.CANCELLING
            ]
        flow_runs = anyio.run(_get_prefect_flow_runs, prefect_states, ["pygeoapi"])
        seen_flows = {}
        jobs = []
        for flow_run in flow_runs:
            if flow_run.flow_id not in seen_flows:
                flow = anyio.run(_get_prefect_flow, flow_run.flow_id)
                seen_flows[flow_run.flow_id] = flow
            job_status = self._flow_run_to_job_status(
                flow_run, seen_flows[flow_run.flow_id]
            )
            jobs.append(job_status)
        return len(flow_runs), jobs

    def get_job(self, job_id: str) -> JobStatusInfoInternal:
        """Get a job."""
        flow_run, flow = anyio.run(_get_prefect_flow_run, uuid.UUID(job_id))
        return self._flow_run_to_job_status(flow_run, flow)

    def delete_job(self, job_id: str) -> JobStatusInfoInternal:
        """Delete a job and associated results/ouptuts."""
        ...

    def _select_execution_mode(
            self,
            requested: RequestedProcessExecutionMode | None,
            processor: BaseProcessor
    ) -> tuple[ProcessExecutionMode, dict[str, str]]:
        chosen_mode, additional_headers = super()._select_execution_mode(
            requested, processor)
        has_deployment = processor.deployment_info is not None
        if chosen_mode == ProcessExecutionMode.async_execute and not has_deployment:
            logger.warning(
                "Cannot run asynchronously on non-deployed processes - "
                "Switching to sync"
            )
            chosen_mode = ProcessExecutionMode.sync_execute
            additional_headers['Preference-Applied'] = (
                RequestedProcessExecutionMode.wait.value)
        return chosen_mode, additional_headers

    def _execute_base_prefect_processor(
            self,
            processor: BasePrefectProcessor,
            chosen_mode: ProcessExecutionMode,
            execution_request: ExecuteRequest,
            *,
            flow_run_name: str,
            tags: list[str],
    ) -> JobStatusInfoInternal:
        """Execute custom prefect processor.

        Execution is triggered by one of three ways:

        - if there is a deployment for the process, then run wherever the
          deployment is housed. Depending on the chosen execution mode, runs
          either:
            - asynchronously
            - synchronously
        - If there is no deployment for the process, then run locally and
          synchronously
        """
        if chosen_mode == ProcessExecutionMode.async_execute:
            logger.debug(f'asynchronous execution')
            flow_run_result = anyio.run(
                run_deployment_async,
                flow_run_name,
                execution_request.dict(by_alias=True),
                tags,
            )
        else:
            logger.debug(f'synchronous execution')
            if processor.deployment_info is not None:
                flow_run_result = run_deployment(
                    name=flow_run_name,
                    parameters=execution_request.dict(by_alias=True),
                    tags=tags,
                )
            else:  # run the flow locally
                flow_run_result = processor.process_flow(
                    execution_request.dict(by_alias=True))
        return self.get_job(flow_run_result.flow_id)

    def _execute_base_processor(
            self,
            processor: BaseProcessor,
            chosen_mode: ProcessExecutionMode,
            execution_request: ExecuteRequest
    ) -> JobStatusInfoInternal:
        executor = flow(
            processor.execute,
            version=processor.process_description.version,
            flow_run_name=f"pygeoapi-job-{execution_request.job_id}",
            validate_parameters=True  # this should be configurable
            # task_runner=None  # this should be configurable
            # retries=None  # this should be configurable
            # retry_delay_seconds=None  # this should be configurable
            # timeout_seconds=None  # this should be configurable
        )
        return executor(
            job_id,
            execution_request,
            results_storage_root=self.output_dir,
            progress_reporter=self.update_job
        )

    def execute_process(
            self,
            process_id: str,
            execution_request: ExecuteRequest,
            requested_execution_mode: RequestedProcessExecutionMode | None = None,
    ) -> tuple[JobStatusInfoInternal, dict[str, str] | None]:
        """Process execution handler.

        This manager is able to execute two types of processes:

        - Normal pygeoapi processes, i.e. those that derive from
          `pygeoapi.process.base.BaseProcessor`. These are made into prefect flows and
          are run with prefect.
        - Custom prefect-aware processes, which derive from
          `pygeoapi_prefect.processes.base.BasePrefectProcessor`. These are able to take
          full advantage of prefect's features
        """
        processor = self.get_processor(process_id)
        chosen_mode, additional_headers = self._select_execution_mode(
            requested_execution_mode, processor)
        flow_run_name = (
            f"{processor.process_description.id}/"
            f"{processor.deployment_info.name}"
        )
        tags = [
            "pygeoapi",
            processor.process_description.id,
        ]
        match processor:
            case BasePrefectProcessor():
                logger.warning("This is a BasePrefectProcessor subclass")
                job_status = self._execute_base_prefect_processor(
                    processor, chosen_mode, execution_request,
                    flow_run_name=flow_run_name,
                    flow_run_tags=tags
                )
            case _:
                logger.warning("This is a standard process")
                executor = flow(
                    processor.execute,
                    version=processor.process_description.version,
                    flow_run_name=f"pygeoapi-job-{execution_request.job_id}",
                    validate_parameters=True  # this should be configurable
                    # task_runner=None  # this should be configurable
                    # retries=None  # this should be configurable
                    # retry_delay_seconds=None  # this should be configurable
                    # timeout_seconds=None  # this should be configurable
                )
                job_status = executor(
                    job_id,
                    execution_request,
                    results_storage_root=self.output_dir,
                    progress_reporter=self.update_job
                )
        return job_status, additional_headers

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
        self, flow_run: FlowRun, prefect_flow: Flow
    ) -> JobStatusInfoInternal:
        return JobStatusInfoInternal(
            jobID=str(flow_run.id),
            status=self.prefect_state_map[flow_run.state_type],
            processID=prefect_flow.name,
            created=flow_run.created,
            started=flow_run.start_time,
            finished=flow_run.end_time,
        )


async def run_deployment_async(
        deployment_name: str, parameters: dict, tags: list[str]):
    """Run a deployed pygeoapi process with prefect."""
    async with get_client() as client:
        deployment = await client.read_deployment_by_name(deployment_name)
        flow_run = await client.create_flow_run_from_deployment(
            deployment.id,
            parameters=parameters,
            state=Scheduled(),
            tags=tags,
        )
        return flow_run


async def _get_prefect_flow_runs(
    states: list[StateType] | None = None, tags: list[str] | None = None
) -> list[FlowRun]:
    if states is not None:
        state_filter = filters.FlowRunFilterState(
            type=filters.FlowRunFilterStateType(any_=states)
        )
    else:
        state_filter = None
    if tags is not None:
        tags_filter = filters.FlowRunFilterTags(all_=tags)
    else:
        tags_filter = None
    async with get_client() as client:
        response = await client.read_flow_runs(
            flow_run_filter=filters.FlowRunFilter(tags=tags_filter, state=state_filter)
        )
    return response


async def _get_prefect_flow_run(flow_run_id: uuid.UUID) -> tuple[FlowRun, Flow]:
    async with get_client() as client:
        flow_run = await client.read_flow_run(flow_run_id)
        prefect_flow = await client.read_flow(flow_run.flow_id)
        return flow_run, prefect_flow


async def _get_prefect_flow(flow_id: uuid.UUID) -> Flow:
    async with get_client() as client:
        return await client.read_flow(flow_id)
