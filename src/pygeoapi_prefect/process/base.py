import abc
import logging
from pathlib import Path
from typing import (
    Any,
    Callable,
    Protocol,
)

from prefect import Flow
from pygeoapi.process.base import BaseProcessor

from .. import schemas

logger = logging.getLogger(__name__)


class PygeoapiPrefectFlowProtocol(Protocol):

    def __call__(
            self,
            *args,
            job_id: str,
            result_storage_block: str | None,
            process_description: schemas.ProcessDescription,
            execution_request: schemas.ExecuteRequest,
    ) -> schemas.JobStatusInfoInternal:
        """Protocol that flows must implement in order to be callable from pygeoapi"""


class BasePrefectProcessor(abc.ABC):
    deployment_info: schemas.PrefectDeployment | None
    process_description: schemas.ProcessDescription | None
    process_flow: PygeoapiPrefectFlowProtocol
    result_storage_block: str | None

    def __init__(
            self,
            deployment_info: schemas.PrefectDeployment | None = None,
            result_storage_block: str | None = None,
    ) -> None:
        """Instantiate a prefect processor.

        Note that because initialization is solely performed by the pygeoapi
        process manager, and this protocol caters exclusively to
        prefect-enabled processors, we are able to specify a custom
        initialization that takes concrete arguments, rather than the usual
        dict that pygeoapi provides to vanilla processes.

        Prefect-related processors are not expected to work with any other
        process managers rather than the
        `pygeoapi_prefect.manager.PrefectManager` one, as they require
        a running prefect instance.
        """
        self.deployment_info = deployment_info
        self.result_storage_block = result_storage_block

    @property
    def metadata(self) -> dict[str, Any]:
        return (
            self.process_description.model_dump(exclude_none=True, by_alias=True)
            if self.process_description else {}
        )


class OldBasePrefectProcessor(BaseProcessor, abc.ABC):
    deployment_info: schemas.PrefectDeployment | None
    result_storage_block: str | None

    def __init__(self, processor_def: dict):
        super().__init__(processor_def, process_metadata=None)
        if (depl := processor_def.get("prefect", {}).get("deployment")) is not None:
            self.deployment_info = schemas.PrefectDeployment(
                depl["name"],
                depl["queue"],
                storage_block=depl.get("storage_block"),
                storage_sub_path=depl.get("storage_sub_path"),
            )
        else:
            self.deployment_info = None
        if (sb := processor_def.get("prefect", {}).get("result_storage")) is not None:
            self.result_storage_block = sb

    @property
    def metadata(self) -> dict:
        """Compatibility with pygeoapi's BaseProcessor.

        Contrary to pygeoapi, which stores process metadata as a plain dictionary,
        pygeoapi-prefect rather uses a `schemas.ProcessDescription` instance instead.
        As pygeoapi expects to be able to read a processor property
        named `metadata` this property converts the process_description into
        a dict when needed.
        """

        # do we even need this? - maybe the pygeoapi.openapi needs it?
        return self.process_description.dict(exclude_none=True, by_alias=True)

    @metadata.setter
    def metadata(self, metadata: dict):
        """Compatibility with pygeoapi's BaseProcessor.

        pygeoapi-prefect does not store processor description as a plain
        dict.

        This setter does nothing. A processor's metadata is not supposed to
        change at runtime - therefore, the only time it is written into is
        during initialization. Since pygeoapi-prefect expects to get processor
        info from the `process_description` property and uses this `metadata`
        property just for compatibility with pygeoapi, it is safe to ignore
        attempts at writing to `self.metadata`
        """
        pass

    @property
    @abc.abstractmethod
    def process_description(self) -> schemas.ProcessDescription:
        """Return process-related description.

        Note that derived classes are free to implement this as either a
        property function or, perhaps more simply, as a class variable. Look
        at ``pygeoapi.process.hello_world.HelloWorldProcessor`` for an
        example.
        """
        ...

    @property
    @abc.abstractmethod
    def process_flow(self) -> Flow: ...

    def execute(
        self,
        job_id: str,
        execution_request: schemas.ExecuteRequest,
        results_storage_root: Path,
        progress_reporter: Callable[[schemas.JobStatusInfoInternal], bool]
        | None = None,
    ) -> schemas.JobStatusInfoInternal:
        """Execute process.

        When implementing processes as prefect flows be sure to also use the
        pygeoapi-prefect process manager.
        """
        raise RuntimeError(
            "This processor is supposed to be run with the pygeoapi prefect "
            "manager, which will never call process.execute()"
        )
        # if self.deployment_info is not None:
        #     if process_async:
        #         flow_run_result = anyio.run(
        #             run_deployment_async,
        #             f"{self.process_metadata.id}/{self.deployment_info.name}",
        #             {**data_dict, "pygeoapi_job_id": job_id},
        #             ["pygeoapi", self.process_metadata.id],
        #         )
        #         result = ("application/json", None, schemas.JobStatus.accepted)
        #     else:
        #         flow_run_result = run_deployment(
        #             name=f"{self.process_metadata.id}/{self.deployment_info.name}",
        #             parameters={
        #                 "pygeoapi_job_id": job_id,
        #                 **data_dict,
        #             },
        #             tags=["pygeoapi", self.process_metadata.id],
        #         )
        #         result = ("application/json", None, schemas.JobStatus.successful)
        #     logger.warning(f"deployment result: {result}")
        # else:
        #     logger.warning(
        #         "Cannot run asynchronously on non-deployed processes - ignoring "
        #         "`is_async` parameter..."
        #     )
        #     flow_run_result = self.process_flow(job_id, **data_dict)
        #     result = ("application/json", None, schemas.JobStatus.successful)
        # return result
