"""pygeoapi process manager based on Prefect."""

import logging
import uuid
from typing import (
    Any,
    Optional,
)

import anyio
import httpx
from prefect import flow
from prefect.blocks.core import Block
from prefect.client.orchestration import get_client
from prefect.client.schemas import FlowRun
from prefect.deployments import run_deployment
from prefect.exceptions import MissingResult
from prefect.server.schemas import filters
from prefect.server.schemas.core import Flow
from prefect.server.schemas.states import StateType
from prefect.task_runners import ConcurrentTaskRunner

from pygeoapi.process.base import (
    BaseProcessor,
    JobNotFoundError,
)
from pygeoapi.process.manager.base import BaseManager
from pygeoapi.util import JobStatus

from .process.base import BasePrefectProcessor
from .schemas import (
    ExecuteRequest,
    JobStatusInfoInternal,
    ProcessExecutionMode,
    OutputExecutionResultInternal,
    RequestedProcessExecutionMode,
)

logger = logging.getLogger(__name__)


class PrefectManager(BaseManager):
    """Prefect-powered pygeoapi manager.

    This manager equates pygeoapi jobs with prefect flow runs.

    Although flow runs have a `flow_run_id`, which could be used as the
    pygeoapi `job_id`, this manager does not use them and instead relies on
    setting a flow run's `name` and use that as the equivalent to the pygeoapi
    job id.
    """

    # is_async: bool = True
    _flow_run_name_prefix = "pygeoapi_job_"

    def __init__(self, manager_def: dict):
        super().__init__(manager_def)
        self.is_async = True

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
    ) -> list[JobStatusInfoInternal]:
        """Get a list of jobs, optionally filtered by relevant parameters.

        Job list filters are not implemented in pygeoapi yet though, so for
        the moment it is not possible to use them for filtering jobs.
        """
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
        try:
            flow_runs = anyio.run(
                _get_prefect_flow_runs, prefect_states, self._flow_run_name_prefix
            )
        except httpx.ConnectError as err:
            # TODO: would be more explicit to raise an exception,
            #  but pygeoapi is not able to handle this yet
            logger.error(f"Could not connect to prefect server: {str(err)}")
            flow_runs = []

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
        return jobs

    def _job_id_to_flow_run_name(self, job_id: str) -> str:
        """Convert input job_id onto corresponding prefect flow_run name."""
        return f"{self._flow_run_name_prefix}{job_id}"

    def _flow_run_name_to_job_id(self, flow_run_name: str) -> str:
        """Convert input flow_run name onto corresponding pygeoapi job_id."""
        return flow_run_name.replace(self._flow_run_name_prefix, "")

    def get_job(self, job_id: str) -> JobStatusInfoInternal:
        """Get job details."""
        flow_run_name = self._job_id_to_flow_run_name(job_id)
        try:
            flow_run_details = anyio.run(_get_prefect_flow_run, flow_run_name)
        except httpx.ConnectError as err:
            # TODO: would be more explicit to raise an exception,
            #  but pygeoapi is not able to handle this yet
            logger.error(f"Could not connect to prefect server: {str(err)}")
            flow_run_details = None

        if flow_run_details is None:
            raise JobNotFoundError()
        else:
            flow_run, prefect_flow = flow_run_details
            return self._flow_run_to_job_status(flow_run, prefect_flow)

    def delete_job(  # type: ignore[empty-body]
        self, job_id: str
    ) -> JobStatusInfoInternal:
        """Delete a job and associated results/ouptuts."""
        pass

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
            flow_fn = processor.process_flow
            flow_fn.flow_run_name = self._job_id_to_flow_run_name(job_id)
            flow_fn.persist_result = True
            flow_fn.log_prints = True
            if chosen_mode == ProcessExecutionMode.sync_execute:
                logger.info("synchronous execution without deployment")
                processor.process_flow(**run_params)
            else:
                raise NotImplementedError("Cannot run regular processes async")
        else:
            # if there is a deployment, then we must rely on the flow function
            # having been explicitly configured to:
            # - persist results
            # - log prints
            #
            # deployed flows cannot be modified in the same way as local ones
            deployment_name = (
                f"{processor.process_description.id}/{processor.deployment_info.name}"
            )
            run_kwargs = {
                "name": deployment_name,
                "parameters": run_params,
                "flow_run_name": self._job_id_to_flow_run_name(job_id),
            }
            if chosen_mode == ProcessExecutionMode.sync_execute:
                logger.info("synchronous execution with deployment")
                run_deployment(**run_kwargs)
            else:
                logger.info("asynchronous execution")
                run_deployment(
                    **run_kwargs, timeout=0  # has the effect of returning immediately
                )
        updated_status_info = self.get_job(job_id)
        logger.info(f"updated_status_info: {updated_status_info}")
        return updated_status_info

    def _execute_base_processor(
        self,
        job_id: str,
        processor: BaseProcessor,
        execution_request: ExecuteRequest,
    ) -> JobStatusInfoInternal:
        """Execute a regular pygeoapi process via prefect."""

        execution_parameters = execution_request.dict(by_alias=True)

        @flow(
            name=processor.metadata["id"],
            version=processor.metadata["version"],
            flow_run_name=self._job_id_to_flow_run_name(job_id),
            persist_result=True,
            log_prints=True,
            validate_parameters=True,
            task_runner=ConcurrentTaskRunner(),  # this should be configurable
            retries=0,  # this should be configurable
            retry_delay_seconds=0,  # this should be configurable
            timeout_seconds=None,  # this should be configurable
        )
        def executor(data_: dict):
            """Run a vanilla pygeoapi process as a prefect flow.

            Since we are adapting a vanilla pygeoapi processor to run with
            prefect, we must ensure the processor is called with the expected
            parameters.
            """
            return processor.execute(data_)

        return executor(execution_parameters)

    def execute_process(
        self,
        process_id: str,
        data_dict: dict,
        execution_mode: Optional[RequestedProcessExecutionMode] = None,
    ) -> tuple[str, Any, JobStatus, Optional[dict[str, str]]]:
        """pygeoapi compatibility method.

        Contrary to pygeoapi, which stores requested execution parameters as
        a plain dictionary, pygeoapi-prefect rather uses a
        `schemas.ExecuteRequest` instance instead - this allows parsing the
        input data with the pydantic models crafted from the OGC API -
        Processes schemas. Thus, this method performs a light validation of the
        input data, converts it from a dict to a proper ExecuteRequest and
        forwards it to the `_execute` method, where execution is handled.
        Finally, it receives whatever results are generated and converts
        back to the data structure expected by pygeoapi.
        """
        # this can raise a pydantic validation error
        execution_request = ExecuteRequest(**data_dict)

        job_status, additional_headers = self._execute(
            process_id=process_id,
            execution_request=execution_request,
            requested_execution_mode=execution_mode,
        )
        return (
            job_status.job_id,
            None,  # mimetype?
            None,  # outputs?
            job_status.status,
            additional_headers,
        )

    def _execute(
        self,
        process_id: str,
        execution_request: ExecuteRequest,
        requested_execution_mode: RequestedProcessExecutionMode | None = None,
    ) -> tuple[JobStatusInfoInternal, dict[str, str] | None]:
        """Process execution handler.

        This manager is able to execute two types of processes:

        - Normal pygeoapi processes, i.e. those that derive from
          `pygeoapi.process.base.BaseProcessor`. These are made into prefect flows
          and are run with prefect. These always run locally.

        - Custom prefect-aware processes, which derive from
          `pygeoapi_prefect.processes.base.BasePrefectProcessor`. These are able to take
          full advantage of prefect's features, which includes running elsewhere, as
          defined by deployments.
        """
        processor = self.get_processor(process_id)
        chosen_mode, additional_headers = self._select_execution_mode(
            requested_execution_mode, processor
        )
        job_id = str(uuid.uuid4())
        if isinstance(processor, BasePrefectProcessor):
            job_status = self._execute_prefect_processor(
                job_id, processor, chosen_mode, execution_request
            )
        else:
            job_status = self._execute_base_processor(
                job_id, processor, execution_request
            )
        return job_status, additional_headers

    def get_output_data_raw(
        self, generated_output: OutputExecutionResultInternal, process_id: str
    ) -> bytes:
        """Get output data as bytes."""
        processor = self.get_processor(process_id)
        if isinstance(processor, BasePrefectProcessor):
            if (sb := processor.result_storage_block) is not None:
                file_system = Block.load(sb)
                result = file_system.read_path(generated_output.location)
            else:
                result = super().get_output_data_raw(generated_output, process_id)
        else:
            result = super().get_output_data_raw(generated_output, process_id)
        return result

    def get_output_data_link_href(
        self, generated_output: OutputExecutionResultInternal, process_id: str
    ) -> str:
        # we need to convert internal location into a proper href for a link
        return super().get_output_data_link_href(generated_output, process_id)

    def _flow_run_to_job_status(
        self, flow_run: FlowRun, prefect_flow: Flow
    ) -> JobStatusInfoInternal:
        job_id = self._flow_run_name_to_job_id(flow_run.name)
        try:
            partial_info = flow_run.state.result()
            generated_outputs = partial_info.generated_outputs
        except MissingResult as err:
            logger.warning(f"Could not get flow_run results: {err}")
            generated_outputs = None
        execution_request = ExecuteRequest(**flow_run.parameters["execution_request"])
        return JobStatusInfoInternal(
            jobID=job_id,
            status=self.prefect_state_map[flow_run.state_type],
            processID=prefect_flow.name,
            created=flow_run.created,
            started=flow_run.start_time,
            finished=flow_run.end_time,
            requested_response_type=execution_request.response,
            requested_outputs=execution_request.outputs,
            generated_outputs=generated_outputs,
        )


async def _get_prefect_flow_runs(
    states: list[StateType] | None = None, name_like: str | None = None
) -> list[FlowRun]:
    """Retrieve existing prefect flow_runs, optionally filtered by state and name"""
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


async def _get_prefect_flow_run(flow_run_name: str) -> tuple[FlowRun, Flow] | None:
    """Retrieve prefect flow_run details."""
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
    """Retrive prefect flow details."""
    async with get_client() as client:
        return await client.read_flow(flow_id)
