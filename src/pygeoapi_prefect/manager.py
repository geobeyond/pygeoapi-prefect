"""pygeoapi process manager based on Prefect."""

import copy
import logging
import uuid
from collections.abc import (
    Mapping,
    Sequence,
)
from typing import (
    Any,
    cast,
)

import httpx
import jsonschema.exceptions
import jsonschema.validators
from prefect.client.schemas import (
    FlowRun,
    StateType,
)
from prefect.client.schemas.objects import Flow
from prefect.deployments import run_deployment
from prefect.results import (
    ResultRecord,
    ResultStore,
)

from pygeoapi.process.base import (
    BaseProcessor,
    JobNotFoundError,
    ProcessorExecuteError,
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
from .process import PrefectDeploymentProcessor
from .protocols import InspectableProcessorProtocol
from .schemas import (
    ExecutionOutput,
    JobList,
    JobOutputs,
    JobStatusInfoInternal,
    JobStatusInfo,
    MediaType,
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
    enable_async_job_execution: bool
    enable_sync_job_execution: bool
    supports_subscribing: bool
    name: str
    # connection: Any = None
    # output_dir: Path | None = None
    sync_job_execution_timeout_seconds: int

    def __init__(self, manager_def: dict[str, Any]):
        self.enable_async_job_execution = manager_def.get(
            "enable_async_job_execution", True
        )
        self.enable_sync_job_execution = manager_def.get(
            "enable_sync_job_execution", False
        )
        self.name = ".".join((self.__class__.__module__, self.__class__.__qualname__))
        self._processor_configurations = {}
        self.sync_job_execution_timeout_seconds = max(
            1, manager_def.get("sync_job_execution_timeout_seconds", 60)
        )
        for id_, resource_conf in manager_def.get("processes", {}).items():
            self._processor_configurations[ProcessId(id_)] = copy.deepcopy(
                resource_conf
            )
            print(f"Validating processor {id_!r}...")
            self._validate_processor_configuration(self.get_processor(id_))

    def _validate_processor_configuration(
        self, processor: InspectableProcessorProtocol
    ) -> None:
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
            print(f"Validating parameter: {param_type=} {param_id=} {param_conf=}")
            try:
                param_schema = param_conf["schema"]
                print(f"{param_schema=}")
                # this is a workaround for dealing with https://github.com/geopython/pygeoapi/issues/2316
                if param_schema.get("type") == "bool":
                    mutated_schema = dict(param_schema)
                    mutated_schema["type"] = "boolean"
                    print(f"{mutated_schema=}")
                    jsonschema.validators.Draft202012Validator.check_schema(
                        mutated_schema
                    )
                else:
                    jsonschema.validators.Draft202012Validator.check_schema(
                        param_schema
                    )
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
    def processes(self) -> dict[ProcessId, dict]:
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
    ) -> dict[str, list[dict[str, Any]] | int]:
        """Get a list of jobs, optionally filtered by relevant parameters.

        Job list filters are not implemented in pygeoapi yet though, so for
        the moment it is not possible to use them for filtering jobs.
        """
        logger.debug(f"get_jobs called with {locals()=}")
        if status:
            prefect_states = [k for k, v in PREFECT_STATE_MAP.items() if status == v]
        else:
            prefect_states = [
                StateType.RUNNING,
                StateType.COMPLETED,
                StateType.CRASHED,
                StateType.CANCELLED,
                StateType.CANCELLING,
            ]
        try:
            flow_runs, total_matched = prefect_client.list_flow_runs(
                prefect_states,
                PygeoapiPrefectJobId.FLOW_RUN_NAME_PREFIX,
                (limit if limit is not None else self._DEFAULT_PROCESS_LIST_LIMIT),
                (offset if offset is not None else self._DEFAULT_PROCESS_LIST_LIMIT),
            )
            print(f"{flow_runs=}")
        except httpx.ConnectError as err:
            # TODO: would be more explicit to raise an exception,
            #  but pygeoapi is not able to handle this yet
            logger.error(f"Could not connect to prefect server: {str(err)}")
            return JobList(jobs=[], number_matched=0).to_pygeoapi()

        seen_flows = {}
        jobs = []
        for flow_run in flow_runs:
            if flow_run.flow_id not in seen_flows:
                seen_flows[flow_run.flow_id] = prefect_client.get_flow(flow_run.flow_id)
            jobs.append(
                self.get_job_status_from_flow_run(
                    flow_run, seen_flows[flow_run.flow_id]
                )
            )
        return JobList(jobs=jobs, number_matched=total_matched).to_pygeoapi()

    def get_job(self, job_id: str) -> dict:
        """Get job details from a Prefect flow run."""
        try:
            flow_run_details = prefect_client.get_flow_run(
                PygeoapiPrefectJobId(job_id).to_flow_run_name()
            )
        except httpx.ConnectError as err:
            # TODO: would be more explicit to raise an exception,
            #  but pygeoapi is not able to handle this yet
            logger.error(f"Could not connect to prefect server: {str(err)}")
            flow_run_details = None

        if flow_run_details is None:
            raise JobNotFoundError()
        else:
            flow_run, prefect_flow = flow_run_details
            return self.get_job_status_from_flow_run(
                flow_run, prefect_flow
            ).to_pygeoapi()

    def get_job_result(self, job_id: str) -> tuple[MediaType, Any]:
        try:
            flow_run_details = prefect_client.get_flow_run(
                PygeoapiPrefectJobId(job_id).to_flow_run_name()
            )
        except httpx.ConnectError as err:
            # TODO: would be more explicit to raise an exception,
            #  but pygeoapi is not able to handle this yet
            logger.error(f"Could not connect to prefect server: {str(err)}")
            flow_run_details = None
        if flow_run_details is None:
            raise JobNotFoundError()
        else:
            flow_run, prefect_flow = flow_run_details
            if not flow_run.state_type == StateType.COMPLETED:
                raise RuntimeError("Job is not completed")
            process_id = ProcessId(prefect_flow.name)
            processor = self.get_processor(process_id)
            print(f"{processor=}")
            if isinstance(processor, PrefectDeploymentProcessor):
                return _retrieve_result_from_prefect(
                    result_storage_block=processor.deployment_info.result_storage_block,
                    result_storage_key=processor.deployment_info.result_storage_key_template.format(job_id=job_id),
                )
            else:
                return _retrieve_result_from_prefect(
                    result_storage_block=None,
                    result_storage_key=f"{job_id}.pickle",
                )

    def delete_job(
        self, job_id: str
    ) -> None:
        """Delete a job and associated results/outputs."""
        raise NotImplementedError

    def get_processor(self, process_id: ProcessId) -> InspectableProcessorProtocol:
        if (resource_conf := self._processor_configurations.get(process_id)) is None:
            raise UnknownProcessError(f"processor with id {process_id!r} is not known")

        default_job_control_options = []
        if self.enable_sync_job_execution:
            default_job_control_options.append(
                ProcessJobControlOption.SYNC_EXECUTE.value
            )
        if self.enable_async_job_execution:
            default_job_control_options.append(
                ProcessJobControlOption.ASYNC_EXECUTE.value
            )
        job_control_options = [
            ProcessJobControlOption(v)
            for v in resource_conf["processor"].get(
                "job_control_options", default_job_control_options
            )
        ]
        if not any(
            (
                ProcessJobControlOption.SYNC_EXECUTE in job_control_options,
                ProcessJobControlOption.ASYNC_EXECUTE in job_control_options,
            ),
        ):
            raise exceptions.InvalidProcessorDefinitionError(
                f"Could not determine job control options for processor {process_id!r}"
            )

        if resource_conf["processor"].get("prefect"):
            processor = PrefectDeploymentProcessor.from_pygeoapi_conf(
                process_id, resource_conf["processor"]
            )
            processor.process_description.job_control_options = job_control_options
        else:
            processor = cast(
                BaseProcessor,
                load_plugin("process", resource_conf["processor"])
            )
            processor.metadata["jobControlOptions"] = job_control_options
        return processor

    def execute_process(
        self,
        process_id: ProcessId,
        data_: dict[str, Any] | None,
        execution_mode: RequestedProcessExecutionMode | None = None,
        requested_outputs: dict[str, dict] | list[str] | None = None,
        subscriber: Subscriber | None = None,
        requested_response: RequestedResponse | None = None,
    ) -> tuple[
        PygeoapiPrefectJobId,
        MediaType | None,
        JobOutputs | None,
        JobStatus,
        ResponseHeaders | None,
    ]:
        if isinstance(requested_outputs, Sequence) and not isinstance(
            requested_outputs, str
        ):
            outs = {out_name: ExecutionOutput() for out_name in requested_outputs}
        elif isinstance(requested_outputs, Mapping):
            outs = {
                out_name: ExecutionOutput(**out_info)
                for out_name, out_info in requested_outputs.items()
            }
        else:
            outs = {}
        inputs = data_ or {}
        processor = self.get_processor(process_id)
        chosen_execution_mode = _select_execution_mode(execution_mode, processor)
        job_id = PygeoapiPrefectJobId(str(uuid.uuid4()))
        response_type = requested_response or RequestedResponse.raw

        if chosen_execution_mode == ProcessExecutionMode.sync_execute and isinstance(
            processor, PrefectDeploymentProcessor
        ):
            media_type, generated_output = _execute_job_sync_via_deployment(
                job_id,
                processor,
                inputs,
                outs,
                response_type,
                timeout_seconds=self.sync_job_execution_timeout_seconds,
                subscriber=subscriber,
            )
            return (
                job_id,
                media_type,
                generated_output,
                JobStatus.successful,
                ResponseHeaders(
                    {"Preference-Applied": RequestedProcessExecutionMode.wait.value}
                ),
            )
        elif chosen_execution_mode == ProcessExecutionMode.sync_execute:
            media_type, generated_output = _execute_job_sync_in_process(
                job_id, processor, inputs, outs, response_type, subscriber
            )
            return (
                job_id,
                media_type,
                generated_output,
                JobStatus.successful,
                ResponseHeaders(
                    {"Preference-Applied": RequestedProcessExecutionMode.wait.value}
                ),
            )
        else:
            response_headers = ResponseHeaders(
                {
                    "Preference-Applied": RequestedProcessExecutionMode.respond_async.value
                }
            )
            job_status = _execute_job_async(
                job_id, processor, inputs, outs, response_type, subscriber
            )
            return job_id, None, None, job_status, response_headers

    def get_job_status_from_flow_run(
        self, flow_run: FlowRun, prefect_flow: Flow
    ) -> JobStatusInfo:
        job_id = PygeoapiPrefectJobId.from_flow_run_name(flow_run.name)
        process_id = ProcessId(prefect_flow.name)
        processor = self.get_processor(process_id)

        return JobStatusInfo(
            job_id=job_id,
            processor_metadata=processor.metadata,
            execution_parameters=flow_run.parameters,
            status=PREFECT_STATE_MAP[flow_run.state_type],
            created=flow_run.created,
            started=flow_run.start_time,
            finished=flow_run.end_time,
        )


def _select_execution_mode(
    requested_mode: RequestedProcessExecutionMode | None,
    processor: BaseProcessor | PrefectDeploymentProcessor,
) -> ProcessExecutionMode:
    requested = requested_mode or RequestedProcessExecutionMode.wait
    if requested == RequestedProcessExecutionMode.wait:
        # client wants sync, is it enabled for the processor?
        is_sync_allowed = (
            ProcessExecutionMode.sync_execute.value
            in processor.metadata["jobControlOptions"]
        )
        chosen = (
            ProcessExecutionMode.sync_execute
            if is_sync_allowed
            else ProcessExecutionMode.async_execute
        )
    else:
        # client wants async, is it enabled for the processor?
        is_async_allowed = (
            ProcessExecutionMode.async_execute.value
            in processor.metadata["jobControlOptions"]
        )
        chosen = (
            ProcessExecutionMode.async_execute
            if is_async_allowed
            else ProcessExecutionMode.sync_execute
        )
    return chosen


def _retrieve_result_from_prefect(
    result_storage_block: str | None,
    result_storage_key: str,
) -> tuple[MediaType, Any]:
    # defer determination of the result storage to Prefect, in order to allow
    # for external configuration
    result_store = ResultStore(result_storage=result_storage_block)
    result_record: ResultRecord = result_store.read(result_storage_key)
    logger.debug(f"debug {result_record=}")
    print(f"print {result_record=}")
    media_type = MediaType(result_record.result[0])
    generated_output = result_record.result[1]
    return media_type, generated_output


def _execute_job_sync_in_process(
    job_id: PygeoapiPrefectJobId,
    processor: BaseProcessor,
    inputs: dict,
    outputs: dict,
    requested_response: RequestedResponse,
    subscriber: Subscriber | None = None,
) -> tuple[MediaType, Any]:
    """Execute job in sync mode.

    Execution is handled by calling the respective Prefect flow.
    """
    configured_flow = vanilla_flow.get_processor_as_flow(processor)
    configured_flow(
        processor.metadata["id"],
        job_id,
        inputs,
        outputs,
    )
    return _retrieve_result_from_prefect(
        result_storage_block=None,
        result_storage_key=f"{job_id}.pickle",
    )


def _execute_job_sync_via_deployment(
    job_id: PygeoapiPrefectJobId,
    processor: PrefectDeploymentProcessor,
    inputs: dict,
    outputs: dict,
    requested_response: RequestedResponse,
    timeout_seconds: int,
    subscriber: Subscriber | None = None,
) -> tuple[MediaType, Any]:
    """Execute job in sync mode.

    Execution is handled by creating a Prefect flow run of the relevant deployment
    and waiting for it to complete.
    """
    job_status = _execute_job_via_deployment(
        deployment_name=processor.deployment_info.name,
        job_id=job_id,
        processor_id=processor.pygeoapi_resource_id,
        inputs=inputs,
        outputs=outputs,
        timeout_seconds=timeout_seconds,
    )
    if job_status not in (JobStatus.successful, JobStatus.failed):
        raise ProcessorExecuteError(
            f"Processor took longer than {timeout_seconds}s to execute"
        )
    return _retrieve_result_from_prefect(
        result_storage_block=processor.deployment_info.result_storage_block,
        result_storage_key=processor.deployment_info.result_storage_key_template.format(job_id=job_id),
    )


def _execute_job_async(
    job_id: PygeoapiPrefectJobId,
    processor: PrefectDeploymentProcessor | BaseProcessor,
    inputs: dict,
    outputs: dict,
    requested_response: RequestedResponse,
    subscriber: Subscriber | None = None,
) -> JobStatus:
    """Execute job in async mode.

    Execution is handled by creating a Prefect flow run of the relevant deployment.
    """
    processor_id = processor.metadata["id"]
    if isinstance(processor, PrefectDeploymentProcessor):
        deployment_name = processor.deployment_info.name
    else:
        deployment_name = (
            f"{processor_id}/{vanilla_flow.get_deployment_name(processor_id)}"
        )
    return _execute_job_via_deployment(
        deployment_name=deployment_name,
        job_id=job_id,
        processor_id=processor_id,
        inputs=inputs,
        outputs=outputs,
        timeout_seconds=0,
    )


def _execute_job_via_deployment(
    deployment_name: str,
    job_id: PygeoapiPrefectJobId,
    processor_id: ProcessId,
    inputs: dict,
    outputs: dict,
    timeout_seconds: int | None,
) -> JobStatus:
    flow_run = run_deployment(
        name=deployment_name,
        flow_run_name=job_id.to_flow_run_name(),
        parameters={
            "processor_id": processor_id,
            "pygeoapi_job_id": job_id,
            "inputs": inputs,
            "outputs": outputs,
        },
        timeout=timeout_seconds
        or 0,  # a value of zero means run in non-blocking fashion (async mode)
    )
    return PREFECT_STATE_MAP[flow_run.state_type]
