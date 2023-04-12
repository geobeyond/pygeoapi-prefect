import dataclasses
import logging

import anyio
from prefect import Flow
from prefect.deployments import (
    Deployment,
    run_deployment,
)
from prefect.blocks.core import Block
from prefect.client.orchestration import get_client
from prefect.states import Scheduled
from pygeoapi.process.base import BaseProcessor
from pygeoapi.util import JobStatus

from pygeoapi_prefect import schemas

LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class PrefectDeployment:
    name: str
    queue: str
    storage_block: str | None = None
    storage_sub_path: str | None = None


async def run_deployment_async(deployment_name: str, parameters: dict, tags: list[str]):
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


class BasePrefectProcessor(BaseProcessor):
    process_flow: Flow
    process_metadata: schemas.Process
    deployment_info: PrefectDeployment | None

    def __init__(self, plugin_definition: dict[str, str]):
        super().__init__(
            plugin_definition,
            self.process_metadata.dict(
                by_alias=True, exclude_none=True, exclude_unset=True)
        )
        if (depl := plugin_definition.get("prefect", {}).get("deployment")) is not None:
            self.deployment_info = PrefectDeployment(
                depl["name"],
                depl["queue"],
                storage_block=depl.get("storage_block"),
                storage_sub_path=depl.get("storage_sub_path"),
            )
        else:
            self.deployment_info = None

    def execute(
            self,
            job_id: str,
            data_dict: dict,
            process_async: bool
    ) -> tuple[str, dict[str, str], JobStatus]:
        """Execute process.

        When implementing processes as prefect flows be sure to also use the
        pygeoapi-prefect process manager.
        """
        if self.deployment_info is not None:
            if process_async:
                flow_run_result = anyio.run(
                    run_deployment_async,
                    f"{self.process_metadata.id}/{self.deployment_info.name}",
                    {**data_dict, "pygeoapi_job_id": job_id},
                    ["pygeoapi", self.process_metadata.id]
                )
                result = ("application/json", None, JobStatus.accepted)
            else:
                flow_run_result = run_deployment(
                    name=f"{self.process_metadata.id}/{self.deployment_info.name}",
                    parameters={
                        "pygeoapi_job_id": job_id,
                        **data_dict,
                    },
                    tags=["pygeoapi", self.process_metadata.id]
                )
                result = ("application/json", None, JobStatus.successful)
            LOGGER.warning(f"deployment result: {result}")
        else:
            LOGGER.warning(
                "Cannot run asynchronously on non-deployed processes - ignoring "
                "`is_async` parameter..."
            )
            flow_run_result = self.process_flow(job_id, **data_dict)
            result = ("application/json", None, JobStatus.successful)
        return result

    def deploy_as_prefect_flow(
            self,
            *,
            deployment_name: str | None = None,
            queue_name: str = "test",
            storage_block_name: str | None = None,
            storage_sub_path: str | None = None,
    ):
        if storage_block_name is not None:
            storage = Block.load(storage_block_name)
        else:
            storage = None

        deployment = Deployment.build_from_flow(
            self.process_flow,
            name=deployment_name or self.name,
            work_queue_name=queue_name,
            storage=storage,
            path=storage_sub_path,
            ignore_file=None,
        )
        deployment.apply()
