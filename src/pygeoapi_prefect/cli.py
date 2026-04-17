import logging
from pathlib import Path

import click
from prefect import serve
from pygeoapi.process.base import BaseProcessor
from pygeoapi.process.manager.base import get_manager
from pygeoapi.util import yaml_load

from .process import PrefectDeploymentProcessor
from .manager import PrefectManager
from .schemas import ProcessId
from . import vanilla_flow

logger = logging.getLogger(__name__)


@click.group(name="prefect")
def root(): ...


@root.command(name="deploy-local")
@click.option("-c", "--pygeoapi-config", type=Path, envvar="PYGEOAPI_CONFIG")
def deploy_processors_locally(
    pygeoapi_config: Path,
):
    """Deploy pygeoapi processes via Prefect, locally."""
    with pygeoapi_config.open() as fh:
        config = yaml_load(fh)
    manager = get_manager(config)
    if not isinstance(manager, PrefectManager):
        raise SystemExit(
            "Cannot deploy as prefect flows - pygeoapi_prefect.PrefectManager "
            "is not being used as the pygeoapi process manager"
        )
    to_serve = []
    for processor_id in manager.processes:
        match processor := manager.get_processor(ProcessId(processor_id)):
            case PrefectDeploymentProcessor():
                logger.debug(
                    f"Skipping process {processor_id!r} - it provides its own "
                    f"deployment configuration"
                )
                continue
            case BaseProcessor():
                configured_flow = vanilla_flow.get_processor_as_flow(processor)
                flow_deployment = configured_flow.to_deployment(
                    name=vanilla_flow.get_deployment_name(processor_id),
                    parameters={"processor_id": processor_id},
                )
                to_serve.append(flow_deployment)
            case _:
                logger.warning(f"Unknown processor type {processor_id}, ignoring...")
                continue
    serve(*to_serve)
