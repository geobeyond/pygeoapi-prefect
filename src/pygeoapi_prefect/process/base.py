import abc
import dataclasses
import logging
from pathlib import Path
from typing import Callable

import pygeoapi.models.processes as schemas
from prefect import Flow
from pygeoapi.process.base import BaseProcessor

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class PrefectDeployment:
    name: str
    queue: str
    storage_block: str | None = None
    storage_sub_path: str | None = None


#
#
# async def run_deployment_async(deployment_name: str, parameters: dict, tags: list[str]):
#     """Run a deployed pygeoapi process with prefect."""
#     async with get_client() as client:
#         deployment = await client.read_deployment_by_name(deployment_name)
#         flow_run = await client.create_flow_run_from_deployment(
#             deployment.id,
#             parameters=parameters,
#             state=Scheduled(),
#             tags=tags,
#         )
#         return flow_run


class BasePrefectProcessor(BaseProcessor):
    deployment_info: PrefectDeployment | None
    result_storage_block: str | None

    def __init__(self, processor_def: dict[str, str]):
        super().__init__(processor_def)
        if (depl := processor_def.get("prefect", {}).get("deployment")) is not None:
            self.deployment_info = PrefectDeployment(
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
    @abc.abstractmethod
    def process_flow(self) -> Flow:
        ...

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
