"""pygeoapi process manager based on Prefect."""

import json
import logging
import uuid
from pathlib import Path
from typing import (
    Any,
    NewType,
    Protocol,
)

import anyio
import httpx
from prefect import flow
from prefect.blocks.core import Block
from prefect.client.schemas import FlowRun
from prefect.deployments import run_deployment
from prefect.exceptions import MissingResult
from prefect.server.schemas.core import Flow
from prefect.server.schemas.states import StateType
from prefect.task_runners import ConcurrentTaskRunner

from pygeoapi.process import exceptions
from pygeoapi.process.base import (
    BaseProcessor,
    ProcessorExecuteError,
)
from pygeoapi.process.manager.base import BaseManager
from pygeoapi.util import (
    JobStatus,
    RequestedProcessExecutionMode,
    RequestedResponse,
    Subscriber,
)

from .process.base import BasePrefectProcessor
from . import prefect_client
from . import schemas

logger = logging.getLogger(__name__)


JobId = NewType("JobId", str)
MediaType = NewType("MediaType", str)
ProcessId = NewType("ProcessId", str)
ResponseHeaders = NewType("ResponseHeaders", dict[str, str])


class PygeoapiProcessorProtocol(Protocol):
    ...


class PygeoapiProcessManagerProtocol(Protocol):

    def __init__(self, manager_def: dict[str, Any]) -> None: ...

    @property
    def is_async(self) -> bool: ...

    @property
    def name(self) -> str: ...

    @property
    def supports_subscribing(self) -> bool: ...

    @property
    def connection(self) -> Any: ...

    @property
    def output_dir(self) -> Path | None: ...

    @property
    def processes(self) -> dict[str, dict[str, Any]]: ...

    def get_processor(
            self,
            process_id: ProcessId
    ) -> PygeoapiProcessorProtocol: ...

    def get_jobs(
            self,
            status: JobStatus,
            limit: int | None = None,
            offset: int | None = None
    ) -> dict[JobId, dict]: ...

    def get_job(self, job_id: JobId) -> dict: ...

    def add_job(self, job_metadata: dict) -> JobId: ...

    def update_job(self, job_id: JobId, job_metadata: dict) -> bool: ...

    def delete_job(self, job_id: JobId) -> bool: ...

    def get_job_result(self, job_id: JobId) -> tuple[MediaType, Any]: ...

    def execute_process(
            self,
            process_id: ProcessId,
            data_: dict,
            execution_mode: RequestedProcessExecutionMode | None = None,
            requested_outputs: dict[str, Any] | None = None,
            subscriber: Subscriber | None = None,
            requested_response: RequestedResponse | None = RequestedResponse.raw.value
    ) -> tuple[
        JobId,
        MediaType,
        JobStatus,
        ResponseHeaders | None
    ]: ...



class PrefectManager(BaseManager):
    """Prefect-powered pygeoapi process manager.

    This manager equates pygeoapi jobs with prefect flow runs.

    Although flow runs have a `flow_run_id`, which could be used as the
    pygeoapi `job_id`, this manager does not use them and instead relies on
    setting a flow run's `name` and use that as the equivalent to the pygeoapi
    job id. This is done in order to provide better visibility of flow runs
    that were dispatched via pygeoapi in the prefect observability tools.
    """

    _FLOW_RUN_NAME_PREFIX = "pygeoapi_job_"

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
    ) -> list[schemas.JobStatusInfoInternal]:
        """Get a list of jobs, optionally filtered by relevant parameters.

        Job list filters are not implemented in pygeoapi yet though, so for
        the moment it is not possible to use them for filtering jobs.
        """
        if status:
            prefect_states = [
                k for k, v in self.prefect_state_map.items() if status == v]
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
                prefect_client.list_flow_runs,
                prefect_states,
                self._FLOW_RUN_NAME_PREFIX
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
                flow = anyio.run(prefect_client.get_flow, flow_run.flow_id)
                seen_flows[flow_run.flow_id] = flow
            job_status = self._flow_run_to_job_status(
                flow_run, seen_flows[flow_run.flow_id]
            )
            jobs.append(job_status)
        return jobs

    def _job_id_to_flow_run_name(self, job_id: str) -> str:
        """Convert input job_id onto corresponding prefect flow_run name."""
        return f"{self._FLOW_RUN_NAME_PREFIX}{job_id}"

    def get_job(self, job_id: str) -> schemas.JobStatusInfoInternal:
        """Get job details."""
        flow_run_name = self._job_id_to_flow_run_name(job_id)
        try:
            flow_run_details = anyio.run(prefect_client.get_flow_run, flow_run_name)
        except httpx.ConnectError as err:
            # TODO: would be more explicit to raise an exception,
            #  but pygeoapi is not able to handle this yet
            logger.error(f"Could not connect to prefect server: {str(err)}")
            flow_run_details = None

        if flow_run_details is None:
            raise exceptions.JobNotFoundError()
        else:
            flow_run, prefect_flow = flow_run_details
            return self._flow_run_to_job_status(flow_run, prefect_flow)

    def delete_job(  # type: ignore [empty-body]
        self, job_id: str
    ) -> schemas.JobStatusInfoInternal:
        """Delete a job and associated results/ouptuts."""
        pass

    def _select_execution_mode(
        self,
        requested: schemas.pygeoapi.util.RequestedProcessExecutionMode | None,
        processor: BaseProcessor,
    ) -> tuple[schemas.ProcessExecutionMode, dict[str, str]]:
        """Select the execution mode to be employed

        The execution mode to use depends on a number of factors:

        - what mode, if any, was requested by the client?
        - does the process support sync and async execution modes?
        - does the process manager support sync and async modes?
        """
        if requested == schemas.RequestedProcessExecutionMode.respond_async:
            # client wants async - do we support it?
            process_supports_async = (
                schemas.ProcessExecutionMode.async_execute.value
                in processor.process_description.job_control_options
            )
            if self.is_async and process_supports_async:
                chosen_mode = schemas.ProcessExecutionMode.async_execute
                additional_headers = {
                    "Preference-Applied": (
                        schemas.RequestedProcessExecutionMode.respond_async.value
                    )
                }
            else:
                chosen_mode = schemas.ProcessExecutionMode.sync_execute
                additional_headers = {
                    "Preference-Applied": (schemas.RequestedProcessExecutionMode.wait.value)
                }
        elif requested == schemas.RequestedProcessExecutionMode.wait:
            # client wants sync - pygeoapi implicitly supports sync mode
            logger.debug("Synchronous execution")
            chosen_mode = schemas.ProcessExecutionMode.sync_execute
            additional_headers = {
                "Preference-Applied": schemas.RequestedProcessExecutionMode.wait.value
            }
        else:  # client has no preference
            # according to OAPI - Processes spec we ought to respond with sync
            logger.debug("Synchronous execution")
            chosen_mode = schemas.ProcessExecutionMode.sync_execute
            additional_headers = {}

        has_deployment = getattr(processor, "deployment_info", None) is not None
        if chosen_mode == schemas.ProcessExecutionMode.async_execute and not has_deployment:
            logger.warning(
                "Cannot run asynchronously on non-deployed processes - "
                "Switching to sync"
            )
            chosen_mode = schemas.ProcessExecutionMode.sync_execute
            additional_headers["Preference-Applied"] = (
                schemas.RequestedProcessExecutionMode.wait.value
            )
        return chosen_mode, additional_headers

    def _execute_prefect_processor(
        self,
        job_id: str,
        processor: BasePrefectProcessor,
        chosen_mode: schemas.ProcessExecutionMode,
        execution_request: schemas.ExecuteRequest,
    ) -> schemas.JobStatusInfoInternal:
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
            if chosen_mode == schemas.ProcessExecutionMode.sync_execute:
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
            if chosen_mode == schemas.ProcessExecutionMode.sync_execute:
                logger.info("synchronous execution with deployment")
                run_deployment(**run_kwargs)
            else:
                logger.info("asynchronous execution")
                run_deployment(
                    **run_kwargs,
                    timeout=0,  # has the effect of returning immediately
                )
        updated_status_info = self.get_job(job_id)
        logger.info(f"updated_status_info: {updated_status_info}")
        return updated_status_info

    def _execute_base_processor(
        self,
        job_id: str,
        processor: BaseProcessor,
        execution_request: schemas.ExecuteRequest,
        # ) -> schemas.JobStatusInfoInternal:
    ) -> tuple[str, Any, JobStatus]:
        """Execute a regular pygeoapi process via prefect.

        This wraps the pygeoapi processor.execute() call in a prefect flow,
        which is then run locally.

        After the process is executed, this method mimics the default pygeoapi
        manager's behavior of saving generated outputs to disk.
        """

        execution_parameters = execution_request.dict(by_alias=True, exclude_none=True)
        input_parameters = execution_parameters.get("inputs", {})
        logger.warning(f"{execution_parameters=}")
        logger.warning(f"{input_parameters=}")

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

        try:
            output_media_type, generated_output = executor(input_parameters)
        except RuntimeError as err:
            # TODO: Change the exception once pygeoapi gets
            #  process-execution-related exceptions in its main process.exceptions
            #  module
            raise ProcessorExecuteError(str(err)) from err
            # raise exceptions.ProcessError() from err
        else:
            # now try to save outputs to local disk, similarly to what the
            # `pygeoapi.BaseManager._execute_handler_sync()` method does
            filename = f"{processor.metadata['id']}-{job_id}"
            job_path = (
                self.output_dir / filename if self.output_dir is not None else None
            )

            if job_path is not None:
                logger.debug(f"writing output to {job_path}")
                if isinstance(generated_output, dict):
                    mode = "w"
                    data = json.dumps(generated_output, sort_keys=True, indent=4)
                    encoding = "utf-8"
                else:
                    mode = "wb"
                    data = generated_output
                    encoding = None
                with job_path.open(mode=mode, encoding=encoding) as fh:
                    fh.write(data)
            return output_media_type, generated_output, JobStatus.successful

    def execute_process(
        self,
        process_id: str,
        data_dict: dict,
        execution_mode: schemas.RequestedProcessExecutionMode | None = None,
    ) -> tuple[
            str, Any, JobStatus, dict[str, str] | None
    ]:
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

        Also, note that current versions of pygeoapi only pass the `inputs`
        property of the execute request to the process manager. Therefore it
        is not possible to respond to additional execution request parameters,
        even if pygeoapi-prefect does support them.

        This means that, for the moment, pygeoapi does not pass other keys in
        the OAPIP `execute.yaml` schema, which are:

        - outputs
        - response
        - subscriber

        for more on this see:

        https://github.com/geopython/pygeoapi/issues/1285

        """
        # execution_request = schemas.ExecuteRequest(**data_dict)

        # this can raise a pydantic validation error
        execution_request = schemas.ExecuteRequest(inputs=data_dict)
        logger.warning(f"{data_dict=}")
        logger.warning(f"{execution_request=}")

        execution_result = self._execute(
            process_id=process_id,
            execution_request=execution_request,
            requested_execution_mode=execution_mode,
        )
        (job_id, output_media_type, generated_output, status, additional_headers) = (
            execution_result
        )
        return (
            job_id,
            output_media_type,
            generated_output,
            status,
            additional_headers,
        )

    def _execute(
        self,
        process_id: str,
        execution_request: schemas.ExecuteRequest,
        requested_execution_mode: schemas.RequestedProcessExecutionMode | None = None,
    ) -> tuple[str, str, Any, JobStatus, dict[str, str]]:
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
            output_media_type, generated_output, current_job_status = None
        else:
            output_media_type, generated_output, current_job_status = (
                self._execute_base_processor(job_id, processor, execution_request)
            )
        # return job_status, additional_headers
        return (
            job_id,
            output_media_type,
            generated_output,
            current_job_status,
            additional_headers,
        )

    def get_output_data_raw(
        self, generated_output: schemas.OutputExecutionResultInternal, process_id: str
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
        self, generated_output: schemas.OutputExecutionResultInternal, process_id: str
    ) -> str:
        # we need to convert internal location into a proper href for a link
        return super().get_output_data_link_href(generated_output, process_id)

    def _flow_run_to_job_status(
        self, flow_run: FlowRun, prefect_flow: Flow
    ) -> schemas.JobStatusInfoInternal:

        job_id = flow_run.name.replace(self._FLOW_RUN_NAME_PREFIX, "")
        try:
            partial_info = flow_run.state.result()
            generated_outputs = partial_info.generated_outputs
        except MissingResult as err:
            logger.warning(f"Could not get flow_run results: {err}")
            generated_outputs = None
        execution_request = schemas.ExecuteRequest(**flow_run.parameters["execution_request"])
        return schemas.JobStatusInfoInternal(
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
