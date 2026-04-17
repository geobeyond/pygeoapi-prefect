import logging
from typing import Any

from . import schemas

logger = logging.getLogger(__name__)


class PrefectDeploymentProcessor:
    deployment_info: schemas.PrefectDeployment
    process_description: schemas.InternalProcessDescription
    pygeoapi_resource_id: schemas.ProcessId

    def __init__(
        self,
        pygeoapi_resource_id: str,
        deployment_info: schemas.PrefectDeployment,
        process_description: schemas.InternalProcessDescription,
    ) -> None:
        self.pygeoapi_resource_id = schemas.ProcessId(pygeoapi_resource_id)
        self.deployment_info = deployment_info
        self.process_description = process_description

    @classmethod
    def from_pygeoapi_conf(
        cls, resource_id: str, resource_configuration: dict
    ) -> "PrefectDeploymentProcessor":
        metadata_conf = resource_configuration["prefect"].get("metadata", {})
        job_control_options = [
            schemas.ProcessJobControlOption(v)
            for v in resource_configuration.get("job_control_options", [])
        ]
        return cls(
            pygeoapi_resource_id=resource_id,
            deployment_info=schemas.PrefectDeployment(
                **resource_configuration["prefect"]["deployment"]
            ),
            process_description=schemas.InternalProcessDescription(
                version=metadata_conf.get("version", "0.0.1-dev"),
                title=metadata_conf.get(
                    "title",
                    (resource_id.replace("-", " ").replace("_", " ").capitalize()),
                ),
                description=metadata_conf.get("description"),
                keywords=metadata_conf.get("keywords", []),
                job_control_options=job_control_options,
                output_transmission=(
                    [
                        schemas.ProcessOutputTransmissionMode(v)
                        for v in metadata_conf.get("outputTransmission", [])
                    ]
                    or [schemas.ProcessOutputTransmissionMode.VALUE]
                ),
                links=(
                    [schemas.Link(**li) for li in metadata_conf.get("links", [])]
                    or None
                ),
                inputs={
                    k: schemas.ProcessInput(**v)
                    for k, v in metadata_conf.get("inputs", {}).items()
                },
                outputs={
                    k: schemas.ProcessOutput(**v)
                    for k, v in metadata_conf.get("outputs", {}).items()
                },
                example=metadata_conf.get("example"),
            ),
        )

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "id": self.pygeoapi_resource_id,
            **self.process_description.model_dump(exclude_none=True, by_alias=True),
        }

    @property
    def name(self) -> str:
        return ".".join((self.__class__.__module__, self.__class__.__qualname__))

    @property
    def supports_outputs(self) -> bool:
        return len(self.process_description.outputs) > 0
