import abc
import logging
from typing import Any

from . import schemas

logger = logging.getLogger(__name__)


class BasePrefectProcessor(abc.ABC):
    deployment_info: schemas.PrefectDeployment
    process_description: schemas.InternalProcessDescription
    pygeoapi_resource_id: str

    def __init__(
            self,
            pygeoapi_resource_id: str,
            deployment_info: schemas.PrefectDeployment,
    ) -> None:
        """Instantiate a prefect processor."""
        self.pygeoapi_resource_id = pygeoapi_resource_id
        self.deployment_info = deployment_info

    @classmethod
    def from_pygeoapi_conf(
            cls,
            resource_id: str,
            resource_configuration: dict
    ) -> "BasePrefectProcessor":
        return cls(
            pygeoapi_resource_id=resource_id,
            deployment_info=schemas.PrefectDeployment(
                **resource_configuration["prefect"]["deployment"])
        )

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "id": self.pygeoapi_resource_id,
            **self.process_description.model_dump(
                exclude_none=True, by_alias=True)
        }

    @property
    def name(self) -> str:
        return ".".join((self.__class__.__module__, self.__class__.__qualname__))

    @property
    def supports_outputs(self) -> bool:
        return len(self.process_description.outputs) > 0

    def set_job_id(self, job_id: str) -> None:
        # unused by prefect-based processors
        pass

    def execute(
            self,
            data: dict[str, Any],
            outputs: list[str] | dict[str, Any] | None = None
    ) -> tuple[str, Any]:
        # unused by prefect-based processors
        pass
