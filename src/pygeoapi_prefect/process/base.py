from prefect import Flow
from prefect.deployments import Deployment
from prefect.blocks.core import Block
from pygeoapi.process.base import BaseProcessor

from pygeoapi_prefect import schemas


class BasePrefectProcessor(BaseProcessor):
    process_flow: Flow
    process_metadata: schemas.Process

    def __init__(self, plugin_definition: dict[str, str]):
        super().__init__(
            plugin_definition,
            self.process_metadata.dict(
                by_alias=True, exclude_none=True, exclude_unset=True)
        )

    def execute(self, job_id: str, data_dict: dict) -> tuple[str, dict[str, str]]:
        """Execute process.

        When implementing processes as prefect flows be sure to also use the
        pygeoapi-prefect process manager.
        """
        # TODO: if there is a deployment we want to use it instead
        return self.process_flow(job_id, **data_dict)

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
