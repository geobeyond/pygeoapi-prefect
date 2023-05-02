"""pygeoapi process manager based on Prefect."""

import logging
import uuid
from pathlib import Path
from typing import (
    Any,
    Callable,
    Optional,
)

import anyio
from prefect import flow
from prefect.client.orchestration import get_client
from prefect.client.schemas import FlowRun
from prefect.deployments import run_deployment
from prefect.exceptions import MissingResult
from prefect.server.schemas import filters
from prefect.server.schemas.core import Flow
from prefect.server.schemas.states import StateType
from prefect.states import Scheduled
from prefect.task_runners import (
    BaseTaskRunner,
    ConcurrentTaskRunner,
)
from pygeoapi.models.processes import (
    ExecuteRequest,
    JobStatus,
    JobStatusInfoInternal,
    ProcessExecutionMode,
    RequestedProcessExecutionMode,
)
from pygeoapi.process import exceptions
from pygeoapi.process.base import BaseProcessor
from pygeoapi.process.manager.base import BaseManager

from .process.base import BasePrefectProcessor

logger = logging.getLogger(__name__)


class PrefectManager(BaseManager):
    """Prefect-powered pygeoapi manager.

    This manager equates pygeoapi jobs with prefect flow runs.

    Although flow runs have a `flow_run_id`, which could be used as the
    pygeoapi `job_id`, this manager does not use them and instead relies on
    setting a flow run's `name` and use that as the equivalent to the pygeoapi
    job id.
    """

    is_async: bool = True
    _flow_run_name_prefix = "pygeoapi_job_"

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
                StateType.CANCELLING,
            ]
        flow_runs = anyio.run(
            _get_prefect_flow_runs, prefect_states, self._flow_run_name_prefix
        )
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

    def _job_id_to_flow_run_name(self, job_id: str) -> str:
        return f"{self._flow_run_name_prefix}{job_id}"

    def _flow_run_name_to_job_id(self, flow_run_name: str) -> str:
        return flow_run_name.replace(self._flow_run_name_prefix, "")

    def get_job(self, job_id: str) -> JobStatusInfoInternal:
        """Get a job."""
        flow_run_name = self._job_id_to_flow_run_name(job_id)
        flow_run_details = anyio.run(_get_prefect_flow_run, flow_run_name)
        if flow_run_details is None:
            raise exceptions.JobNotFoundError()
        else:
            flow_run, prefect_flow = flow_run_details
            return self._flow_run_to_job_status(flow_run, prefect_flow)

    def delete_job(self, job_id: str) -> JobStatusInfoInternal:
        """Delete a job and associated results/ouptuts."""
        ...

    def _select_execution_mode(
        self, requested: RequestedProcessExecutionMode | None, processor: BaseProcessor
    ) -> tuple[ProcessExecutionMode, dict[str, str]]:
        chosen_mode, additional_headers = super()._select_execution_mode(
            requested, processor
        )
        has_deployment = getattr(processor, "deployment_info", None) is not None
        if chosen_mode == ProcessExecutionMode.async_execute and not has_deployment:
            logger.warning(
                "Cannot run asynchronously on non-deployed processes - "
                "Switching to sync"
            )
            chosen_mode = ProcessExecutionMode.sync_execute
            additional_headers[
                "Preference-Applied"
            ] = RequestedProcessExecutionMode.wait.value
        return chosen_mode, additional_headers

    def _execute_prefect_processor(
        self,
        job_id: str,
        processor: BasePrefectProcessor,
        chosen_mode: ProcessExecutionMode,
        execution_request: ExecuteRequest,
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
        run_params = {
            "job_id": job_id,
            "result_storage_block": processor.result_storage_block,
            "process_description": processor.process_description.dict(
                by_alias=True, exclude_none=True
            ),
            "execution_request": execution_request.dict(
                by_alias=True, exclude_none=True
            ),
        }
        if processor.deployment_info is None:  # will run locally and sync
            if chosen_mode == ProcessExecutionMode.sync_execute:
                print(f"synchronous execution without deployment")
                logger.debug(f"synchronous execution")
                flow_fn = processor.process_flow
                flow_fn.flow_run_name = self._job_id_to_flow_run_name(job_id)
                partial_status_info = processor.process_flow(**run_params)
            else:
                raise NotImplementedError("Cannot run regular processes async")
        else:
            deployment_name = (
                f"{processor.process_description.id}/{processor.deployment_info.name}"
            )
            run_kwargs = {
                "name": deployment_name,
                "parameters": run_params,
                "flow_run_name": self._job_id_to_flow_run_name(job_id),
            }
            if chosen_mode == ProcessExecutionMode.sync_execute:
                print(f"synchronous execution with deployment")
                print(f"run_kwargs: {run_kwargs}")
                logger.debug(f"synchronous execution")
                run_deployment(**run_kwargs)
            else:
                print(f"asynchronous execution")
                logger.debug(f"asynchronous execution")
                run_deployment(
                    **run_kwargs, timeout=0  # has the effect of returning immediately
                )
                # flow_run_result = anyio.run(
                #     run_deployment_async,
                #     deployment_name,
                #     job_id,
                #     execution_request.dict(by_alias=True),
                # )
        updated_status_info = self.get_job(job_id)
        print(f"updated_status_info: {updated_status_info}")
        return updated_status_info

    def _execute_base_processor(
        self,
        job_id: str,
        processor: BaseProcessor,
        execution_request: ExecuteRequest,
    ) -> JobStatusInfoInternal:
        """Execute a regular pygeoapi process via prefect."""

        @flow(
            name=processor.process_description.id,
            version=processor.process_description.version,
            flow_run_name=self._job_id_to_flow_run_name(job_id),
            validate_parameters=True,
            task_runner=ConcurrentTaskRunner(),  # this should be configurable
            retries=0,  # this should be configurable
            retry_delay_seconds=0,  # this should be configurable
            timeout_seconds=None,  # this should be configurable
        )
        def executor(
            job_id_: str,
            execution_request_: ExecuteRequest,
            results_storage_root: Path,
            # progress_reporter=Callable[[JobStatusInfoInternal], bool]
        ):
            """Run a vanilla pygeoapi process as a prefect flow."""
            return processor.execute(
                job_id_,
                execution_request_,
                results_storage_root=results_storage_root,
                # progress_reporter=progress_reporter
            )

        # return executor(
        #     job_id, execution_request, self.output_dir, self.update_job)
        return executor(job_id, execution_request, self.output_dir)

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
        print(f"processor: {processor}")
        chosen_mode, additional_headers = self._select_execution_mode(
            requested_execution_mode, processor
        )
        print(f"chosen_mode: {chosen_mode}")
        print(f"additional_headers: {additional_headers}")
        job_id = str(uuid.uuid4())
        print(f"job_id: {job_id}")
        print(f"is prefect processor: {isinstance(processor, BasePrefectProcessor)}")
        if isinstance(processor, BasePrefectProcessor):
            job_status = self._execute_prefect_processor(
                job_id, processor, chosen_mode, execution_request
            )
        else:
            job_status = self._execute_base_processor(
                job_id, processor, execution_request
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
        job_id = self._flow_run_name_to_job_id(flow_run.name)
        try:
            partial_info = flow_run.state.result()
            generated_outputs = partial_info.generated_outputs
        except MissingResult:
            generated_outputs = None
        return JobStatusInfoInternal(
            jobID=job_id,
            status=self.prefect_state_map[flow_run.state_type],
            processID=prefect_flow.name,
            created=flow_run.created,
            started=flow_run.start_time,
            finished=flow_run.end_time,
            generated_outputs=generated_outputs,
        )


async def run_deployment_async(deployment_name: str, parameters: dict):
    """Run a deployed pygeoapi process with prefect asynchronously.

    :param deployment_name: The name of the deployment to run - this is a string
    of the form `flow_name/deployment_name`
    """
    async with get_client() as client:
        deployment = await client.read_deployment_by_name(deployment_name)
        flow_run = await client.create_flow_run_from_deployment(
            deployment.id,
            parameters=parameters,
            state=Scheduled(),
        )
        return flow_run


async def _get_prefect_flow_runs(
    states: list[StateType] | None = None, name_like: str | None = None
) -> list[FlowRun]:
    if states is not None:
        state_filter = filters.FlowRunFilterState(
            type=filters.FlowRunFilterStateType(any_=states)
        )
    else:
        state_filter = None
    if name_like is not None:
        name_like_filter = filters.FlowRunFilterName(like_=name_like)
    else:
        name_like_filter = None
    async with get_client() as client:
        response = await client.read_flow_runs(
            flow_run_filter=filters.FlowRunFilter(
                state=state_filter,
                name=name_like_filter,
            )
        )
    return response


# async def _get_prefect_flow_run(flow_run_id: uuid.UUID) -> tuple[FlowRun, Flow]:
#     async with get_client() as client:
#         flow_run = await client.read_flow_run(flow_run_id)
#         prefect_flow = await client.read_flow(flow_run.flow_id)
#         return flow_run, prefect_flow


async def _get_prefect_flow_run(flow_run_name: str) -> tuple[FlowRun, Flow] | None:
    async with get_client() as client:
        flow_runs = await client.read_flow_runs(
            flow_run_filter=filters.FlowRunFilter(
                name=filters.FlowRunFilterName(any_=[flow_run_name])
            )
        )
        try:
            flow_run = flow_runs[0]
        except IndexError:
            result = None
        else:
            prefect_flow = await client.read_flow(flow_run.flow_id)
            result = flow_run, prefect_flow
        return result


async def _get_prefect_flow(flow_id: uuid.UUID) -> Flow:
    async with get_client() as client:
        return await client.read_flow(flow_id)
