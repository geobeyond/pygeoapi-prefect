"""pygeoapi process manager based on Prefect."""

import copy
import importlib
import json
import logging
import uuid
from collections.abc import (
    Mapping,
    Sequence,
)
from pathlib import Path
from typing import (
    Any,
    Type,
)

import httpx
import jsonschema.exceptions
import jsonschema.validators
from prefect import flow
from prefect.blocks.core import Block
from prefect.client.schemas import FlowRun
from prefect.deployments import run_deployment
from prefect.exceptions import MissingResult
from prefect.results import (
    ResultRecord,
    ResultStore,
)
from prefect.server.schemas.core import Flow
from prefect.server.schemas.states import StateType

from pygeoapi.process.base import (
    BaseProcessor,
    JobNotFoundError,
    ProcessorExecuteError,
    ProcessError,
    UnknownProcessError,
)
from pygeoapi.plugin import load_plugin
from pygeoapi.util import (
    JobStatus,
    ProcessExecutionMode,
    RequestedProcessExecutionMode,
    RequestedResponse,
    Subscriber,
)

from . import (
    exceptions,
    prefect_client,
    vanilla_flow,
)
from .process import BasePrefectProcessor
from .protocols import PygeoapiProcessorProtocol
from .schemas import (
    ExecuteRequest,
    ExecutionOutput,
    JobList,
    JobOutputs,
    JobStatusInfoInternal,
    MediaType,
    OutputExecutionResultInternal,
    PrefectDeployment,
    ProcessId,
    ProcessJobControlOption,
    PygeoapiPrefectJobId,
    ResponseHeaders,
)

logger = logging.getLogger(__name__)


PREFECT_STATE_MAP = {
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


class PrefectManager:
    """Prefect-powered pygeoapi process manager.

    This manager equates pygeoapi jobs with prefect flow runs.

    Although flow runs have a `flow_run_id`, which could be used as the
    pygeoapi `job_id`, this manager does not use them and instead relies on
    setting a flow run's `name` and use that as the equivalent to the pygeoapi
    job id. This is done in order to provide better visibility of flow runs
    that were dispatched via pygeoapi in the prefect observability tools.
    """

    _DEFAULT_PROCESS_LIST_LIMIT = 10
    _DEFAULT_PROCESS_LIST_OFFSET = 0
    _processor_configurations: dict[ProcessId, dict[str, Any]]

    is_async: bool = True
    supports_subscribing: bool
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
    connection: Any = None
    name: str
    output_dir: Path | None = None
    sync_job_execution_timeout_seconds: int

    def __init__(self, manager_def: dict[str, Any]):
        self.name = ".".join(
            (self.__class__.__module__, self.__class__.__qualname__)
        )
        self._processor_configurations = {}
        self.sync_job_execution_timeout_seconds = max(
            1,
            manager_def.get("sync_job_execution_timeout_seconds", 60)
        )
        for id_, resource_conf in manager_def.get("processes", {}).items():
            self._processor_configurations[ProcessId(id_)] = copy.deepcopy(resource_conf)
            print(f"Validating processor {id_!r}...")
            self._validate_processor_configuration(self.get_processor(id_))

    def _validate_processor_configuration(
            self, processor: PygeoapiProcessorProtocol) -> None:
        """Validate a processor configuration's inputs and outputs with jsonschema"""
        io_params = [
            *(
                ("input", id_, conf)
                for id_, conf in processor.metadata.get("inputs", {}).items()
            ),
            *(
                ("output", id_, conf)
                for id_, conf in processor.metadata.get("outputs", {}).items()
            ),
        ]
        for param_type, param_id, param_conf in io_params:
            try:
                param_schema = param_conf["schema"]
                jsonschema.validators.Draft202012Validator.check_schema(
                    param_schema)
            except KeyError as err:
                raise exceptions.InvalidProcessorDefinitionError(
                    f"Invalid configuration: Processor {processor.name!r} - "
                    f"{param_type} {param_id!r} does not contain a 'schema' "
                    f"definition"
                ) from err
            except jsonschema.exceptions.SchemaError as err:
                raise exceptions.InvalidProcessorDefinitionError(
                    f"Invalid configuration: Processor {processor.name!r} - "
                    f"{param_type} {param_id!r} contains an invalid 'schema' "
                    f"definition: {str(err)}"
                ) from err

    @property
    def processes(self) -> dict[str, dict]:
        return copy.deepcopy(self._processor_configurations)

    def get_jobs(
        self,
        status: list[JobStatus] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        *,
        type_: list[str] | None = None,
        process_id: list[str] | None = None,
        date_time: str | None = None,
        min_duration_seconds: int | None = None,
        max_duration_seconds: int | None = None,
    ) -> dict[str, Any]:
        """Get a list of jobs, optionally filtered by relevant parameters.

        Job list filters are not implemented in pygeoapi yet though, so for
        the moment it is not possible to use them for filtering jobs.
        """
        logger.debug(f"get_jobs called with {locals()=}")
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
            flow_runs = prefect_client.list_flow_runs(
                prefect_states,
                PygeoapiPrefectJobId.FLOW_RUN_NAME_PREFIX,
                (limit if limit is not None else self._DEFAULT_PROCESS_LIST_LIMIT),
                (offset if offset is not None else self._DEFAULT_PROCESS_LIST_LIMIT)
            )
            print(f"{flow_runs=}")
        except httpx.ConnectError as err:
            # TODO: would be more explicit to raise an exception,
            #  but pygeoapi is not able to handle this yet
            logger.error(f"Could not connect to prefect server: {str(err)}")
            flow_runs = []

        seen_flows = {}
        jobs = []
        for flow_run in flow_runs:
            if flow_run.flow_id not in seen_flows:
                seen_flows[flow_run.flow_id] = prefect_client.get_flow(flow_run.flow_id)
            jobs.append(
                get_job_status_from_flow_run(flow_run, seen_flows[flow_run.flow_id])
            )
        return JobList(
            jobs=jobs,
            numberMatched=0
        ).model_dump(by_alias=True)

    def get_job(self, job_id: str) -> JobStatusInfoInternal:
        """Get job details."""
        return get_job_status(job_id)

    def delete_job(  # type: ignore [empty-body]
        self, job_id: str
    ) -> JobStatusInfoInternal:
        """Delete a job and associated results/outputs."""
        pass

    def get_processor(self, process_id: ProcessId) -> PygeoapiProcessorProtocol:
        if (resource_conf := self._processor_configurations.get(process_id)) is None:
            raise UnknownProcessError(f"processor with id {process_id!r} is not known")
        if resource_conf["processor"].get("prefect"):
            module_path, processor_type_name = (
                resource_conf["processor"]["name"].rpartition(".")[::2]
            )
            loaded_module = importlib.import_module(module_path)
            processor_type: Type[BasePrefectProcessor] = getattr(
                loaded_module, processor_type_name)
            processor = processor_type.from_pygeoapi_conf(
                process_id, resource_conf["processor"])
            # override whatever job control options there might be on the processor
            processor.process_description.job_control_options = [
                ProcessJobControlOption.SYNC_EXECUTE,
                ProcessJobControlOption.ASYNC_EXECUTE,
            ]
        else:
            processor = load_plugin("process", resource_conf["processor"])
            # override whatever job control options there might be on the processor
            processor.metadata["jobControlOptions"] = [
                ProcessJobControlOption.SYNC_EXECUTE,
                ProcessJobControlOption.ASYNC_EXECUTE,
            ]
        return processor

    def execute_process(
            self,
            process_id: ProcessId,
            data_: dict[str, Any] | None,
            execution_mode: RequestedProcessExecutionMode | None = None,
            requested_outputs: dict[str, dict] | list[str] | None = None,
            subscriber: Subscriber | None = None,
            requested_response: RequestedResponse | None = RequestedResponse.raw
    ) -> tuple[
        PygeoapiPrefectJobId,
        MediaType | None,
        JobOutputs | None,
        JobStatus,
        ResponseHeaders | None
    ]:
        job_id = PygeoapiPrefectJobId(str(uuid.uuid4()))
        response_headers = ResponseHeaders(
            {"Preference-Applied": RequestedProcessExecutionMode.wait.value})
        chosen_mode = ProcessExecutionMode.sync_execute
        if execution_mode == RequestedProcessExecutionMode.respond_async:
            chosen_mode = ProcessExecutionMode.async_execute
            response_headers["Preference-Applied"] = RequestedProcessExecutionMode.respond_async.value

        match processor := self.get_processor(process_id):
            case BasePrefectProcessor():
                deployment_info = processor.deployment_info
            case BaseProcessor():
                deployment_info = PrefectDeployment(
                    name=f"{process_id}/{vanilla_flow.get_deployment_name(process_id)}",
                    result_storage_block=None,
                    result_storage_key_template=f"{job_id}.pickle"
                )
            case _:
                raise ProcessError(f"Unknown processor type {type(processor)!r}")
        if isinstance(requested_outputs, Sequence) and not isinstance(requested_outputs, str):
            outs = {out_name: ExecutionOutput() for out_name in requested_outputs}
        elif isinstance(requested_outputs, Mapping):
            outs = {
                out_name: ExecutionOutput(**out_info)
                for out_name, out_info in requested_outputs.items()
            }
        else:
            outs = None
        execution_request = ExecuteRequest(
            deployment_info=deployment_info,
            inputs=data_,
            outputs=outs,
            response=requested_response,
            subscriber=subscriber,
        )
        if chosen_mode == ProcessExecutionMode.sync_execute:
            media_type, generated_output = self._execute_job_sync(
                job_id, processor, execution_request)
            print(f"{media_type=}")
            print(f"{generated_output=}")
            return job_id, media_type, generated_output, JobStatus.successful, response_headers
        else:
            status = self._execute_job_async(job_id, processor, execution_request)
            return job_id, None, None, status, response_headers

    def _execute_job_async(
            self,
            job_id: PygeoapiPrefectJobId,
            processor: BaseProcessor | BasePrefectProcessor,
            execution_request: ExecuteRequest,
    ) -> JobStatus:
        flow_run = run_deployment(
            name=execution_request.deployment_info.name,
            parameters={
                "processor_id": processor.metadata["id"],
                "pygeoapi_job_id": job_id,
                "inputs": execution_request.inputs,
                "outputs": execution_request.outputs,
            },
            timeout=0  # a value of zero means run in non-blocking fashion
        )
        return self.prefect_state_map[flow_run.state_type]

    def _execute_job_sync(
            self,
            job_id: PygeoapiPrefectJobId,
            processor: BaseProcessor | BasePrefectProcessor,
            execution_request: ExecuteRequest,
    ) -> tuple[MediaType, Any]:
        flow_run = run_deployment(
            name=execution_request.deployment_info.name,
            flow_run_name=job_id.to_flow_run_name(),
            parameters={
                "processor_id": processor.metadata["id"],
                "pygeoapi_job_id": job_id,
                "inputs": execution_request.inputs,
                "outputs": execution_request.outputs,
            },
            timeout=self.sync_job_execution_timeout_seconds
        )
        if flow_run.state_type != StateType.COMPLETED:
            raise ProcessorExecuteError(
                f"Processor took longer than "
                f"{self.sync_job_execution_timeout_seconds}s to execute"
            )

        # defer determination of the result storage to Prefect, in order to allow
        # for external configuration
        result_store = ResultStore(
            result_storage=execution_request.deployment_info.result_storage_block
        )
        result_record: ResultRecord = result_store.read(
            execution_request.deployment_info.result_storage_key_template)
        logger.debug(f"debug {result_record=}")
        print(f"print {result_record=}")
        media_type = MediaType(result_record.result[0])
        generated_output = result_record.result[1]
        return media_type, generated_output


    def get_output_data_raw(
            self,
            generated_output: OutputExecutionResultInternal,
            process_id: ProcessId
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


def get_job_status(job_id: str) -> JobStatusInfoInternal:
    """Get job details from a Prefect flow run."""
    try:
        flow_run_details = prefect_client.get_flow_run(
            PygeoapiPrefectJobId(job_id).to_flow_run_name())
    except httpx.ConnectError as err:
        # TODO: would be more explicit to raise an exception,
        #  but pygeoapi is not able to handle this yet
        logger.error(f"Could not connect to prefect server: {str(err)}")
        flow_run_details = None

    if flow_run_details is None:
        raise JobNotFoundError()
    else:
        flow_run, prefect_flow = flow_run_details
        return get_job_status_from_flow_run(flow_run, prefect_flow)


def get_job_status_from_flow_run(
        flow_run: FlowRun,
        prefect_flow: Flow
) -> JobStatusInfoInternal:
    job_id = PygeoapiPrefectJobId.from_flow_run_name(flow_run.name)
    logger.info(f"{flow_run=}")
    logger.info(f"{flow_run.parameters=}")
    logger.info(f"{job_id=}")
    try:
        media_type, generated_output = flow_run.state.result()
        logger.info(f"{media_type=}")
        logger.info(f"{generated_output=}")
    except MissingResult as err:
        logger.warning(f"Could not get flow_run results: {err}")
        generated_output = None
    execution_request = ExecuteRequest(**flow_run.parameters["execution_request"])
    logger.info(f"{execution_request=}")
    logger.info(f"{flow_run.state_type=}")
    return JobStatusInfoInternal(
        jobID=job_id,
        status=PREFECT_STATE_MAP[flow_run.state_type],
        processID=prefect_flow.name,
        created=flow_run.created,
        started=flow_run.start_time,
        finished=flow_run.end_time,
        requested_response_type=execution_request.response,
        requested_outputs=execution_request.outputs,
        generated_outputs=generated_output,
    )


def execute_vanilla_processor_sync(
        job_id: PygeoapiPrefectJobId,
        processor: PygeoapiProcessorProtocol,
        execution_request: ExecuteRequest,
        output_dir: Path | None,
        prefect_worker_pool: str | None = None,
) -> tuple[MediaType, Any, JobStatus]:
    """Execute a regular pygeoapi processor locally via prefect.

    This wraps the pygeoapi processor.execute() call in a prefect flow,
    which is then run locally in a blocking way.

    This function stores the generated outputs on disk if given an
    `output_dir`. This emulates the same behavior of the base
    pygeoapi prefect manager, which keeps generated files on disk to be able
    to provide clients with means to re-fetch generated files via the
    corresponding jon details page
    """

    @flow(
        name=processor.metadata["id"],
        version=processor.metadata["version"],
        flow_run_name=job_id.to_flow_run_name(),
        persist_result=True,
        log_prints=True,
        validate_parameters=True,
        retries=0,  # this should be configurable
        retry_delay_seconds=0,  # this should be configurable
        timeout_seconds=None,  # this should be configurable
    )
    def executor(data_: dict, outputs=None) -> tuple[str, Any]:
        """Run a vanilla pygeoapi process as a prefect flow.

        Since we are adapting a vanilla pygeoapi processor to run with
        prefect, we must ensure the processor is called with the expected
        parameters.

        The expectations of this function are that the underlying pygeoapi
        processor does whatever computation it needs and then returns a single
        pair of:

        - media_type, which is a string with the media type of the generated output
        - generated output, which is either a `bytes` with the raw output or a
          Python data structure, to be serialized to JSON by the caller, if the
          media_type is set to `application/json`.

        Note that this implies that a processor job is not allowed to generate
        multiple outputs, unless they are packed together (for example as a
        JSON object).
        """
        return processor.execute(data_, outputs)

    execution_parameters = execution_request.model_dump(
        by_alias=True, exclude_none=True)
    try:
        # calling a Prefect flow directly, like we do here, causes it to
        # create a flow_run that executes locally in a blocking fashion -
        # this means it runs in sync mode
        output_media_type, generated_output = executor(
            data_=execution_parameters.get("inputs", {}),
            outputs=execution_parameters.get("outputs")
        )
    except Exception as err:
        raise ProcessorExecuteError(str(err)) from err

    if output_dir:
        file_name = "_".join((processor.metadata["id"], job_id, "output"))
        target_path = output_dir / file_name
        logger.debug(f"Persisting output to disk...")
        if isinstance(generated_output, (dict, list)):
            target_path.write_text(
                json.dumps(generated_output, sort_keys=True, indent=4))
        else:
            target_path.write_bytes(bytes(generated_output))

    return MediaType(output_media_type), generated_output, JobStatus.successful


def execute_prefect_processor(
        job_id: PygeoapiPrefectJobId,
        processor: BasePrefectProcessor,
        chosen_mode: ProcessExecutionMode,
        execution_request: ExecuteRequest,
) -> JobStatusInfoInternal:
    """Execute a prefect-based pygeoapi processor.

    Execution is performed in one of three ways:

    - If there is a deployment for the process, then run wherever the
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
        "process_description": processor.process_description.model_dump(
            by_alias=True, exclude_none=True
        ),
        "execution_request": execution_request.model_dump(
            by_alias=True, exclude_none=True
        ),
    }
    if processor.deployment_info is None:
        flow_fn = processor.process_flow
        flow_fn.flow_run_name = job_id.to_flow_run_name()
        flow_fn.persist_result = True
        flow_fn.log_prints = True
        if chosen_mode == ProcessExecutionMode.sync_execute:
            logger.info("synchronous execution without deployment")
            flow_fn(**run_params)
        else:
            raise NotImplementedError("Cannot run undeployed prefect flows async")
    else:
        # if there is a deployment, then we must rely on the flow function
        # having been explicitly configured to:
        # - persist results
        # - log prints
        #
        # deployed flows cannot be modified in the same way as local ones
        deployment_name = (
            f"{processor.pygeoapi_resource_id}/{processor.deployment_info.name}"
        )
        run_kwargs = {
            "name": deployment_name,
            "parameters": run_params,
            "flow_run_name": job_id.to_flow_run_name(),
        }
        if chosen_mode == ProcessExecutionMode.sync_execute:
            logger.info("synchronous execution with deployment")
            run_deployment(**run_kwargs)
        else:
            logger.info("asynchronous execution")
            run_deployment(
                **run_kwargs,
                timeout=0,  # has the effect of returning immediately
            )
    updated_status_info = get_job_status(job_id)
    logger.info(f"updated_status_info: {updated_status_info}")
    return updated_status_info
