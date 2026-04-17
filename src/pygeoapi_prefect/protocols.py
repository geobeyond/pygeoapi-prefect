from typing import (
    Any,
    Protocol,
    TYPE_CHECKING,
)

from pygeoapi.util import (
    JobStatus,
    RequestedProcessExecutionMode,
    RequestedResponse,
    Subscriber,
)

if TYPE_CHECKING:
    from .schemas import (
        JobOutputs,
        ProcessId,
        PygeoapiPrefectJobId,
        MediaType,
        ResponseHeaders,
    )


class PygeoapiProcessorProtocol(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def metadata(self) -> dict[str, Any]: ...

    @property
    def supports_outputs(self) -> bool: ...

    def set_job_id(self, job_id: str) -> None: ...

    def execute(
        self, data_: dict[str, Any], outputs: list[str] | dict[str, Any] | None = None
    ) -> tuple[str, Any]: ...


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

    # @property
    # def output_dir(self) -> Path | None: ...

    @property
    def processes(self) -> dict[str, dict[str, Any]]:
        """Return processor configurations known to the manager"""

    def get_processor(self, process_id: "ProcessId") -> PygeoapiProcessorProtocol:
        """Instantiate a processor."""

    def get_jobs(
        self,
        status: JobStatus | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Get process-related jobs"""

    def get_job(self, job_id: str) -> dict:
        """Get a process-related job"""

    # add_job is only used internally by BaseProcess instances. Therefore, it
    # should not be part of the protocol. Jobs are created
    # implicitly by calling execute_process
    # def add_job(self, job_metadata: dict) -> JobId: ...

    # update_job is only used internally by BaseProcess instances. Therefore,
    # it should not be part of the protocol. Jobs are updated internally by
    # the handler of execute_process, as the execution progresses
    # def update_job(self, job_id: JobId, job_metadata: dict) -> bool: ...

    def delete_job(self, job_id: str) -> bool: ...

    def get_job_result(self, job_id: str) -> tuple["MediaType", Any]: ...

    def execute_process(
        self,
        process_id: "ProcessId",
        data_: dict,
        execution_mode: RequestedProcessExecutionMode | None = None,
        requested_outputs: dict[str, Any] | None = None,
        subscriber: Subscriber | None = None,
        requested_response: RequestedResponse | None = RequestedResponse.raw,
    ) -> tuple[
        "PygeoapiPrefectJobId", "MediaType", "JobOutputs", JobStatus, "ResponseHeaders" | None
    ]:
        """Execute a process"""


class PygeoapiPrefectFlowProtocol(Protocol):
    def __call__(
        self,
        processor_id: str,
        pygeoapi_job_id: str,
        inputs: dict,
        outputs: dict | None = None,
    ) -> None:
        """Protocol that flows must implement in order to be callable from pygeoapi"""
