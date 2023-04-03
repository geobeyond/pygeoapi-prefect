from pathlib import Path

import click
import yaml
from pygeoapi.plugin import load_plugin

from .process.base import BasePrefectProcessor


@click.group()
def root():
    ...


@root.command()
@click.argument("process_id")
@click.option("-c", "--pygeoapi-config", type=Path, envvar="PYGEOAPI_CONFIG")
@click.option("-q", "--prefect-queue-name", default="test")
@click.option("-n", "--deployment-name", default="test")
@click.option("-s", "--storage-block-name")
@click.option("-p", "--storage-sub-path")
def deploy_process_as_flow(
        process_id: str,
        pygeoapi_config: Path,
        prefect_queue_name: str,
        deployment_name: str,
        storage_block_name: str | None,
        storage_sub_path: str | None,
):
    """Create and apply prefect deployment for PROCESS_ID."""
    with pygeoapi_config.open() as fh:
        config = yaml.safe_load(fh)
    try:
        process_config = config.get("resources", {})[process_id]
    except KeyError as exc:
        raise click.BadParameter(
            f"Process {process_id!r} not found in pygeoapi config") from exc
    else:
        if process_config.get("type", "") == "process":
            process_definition = process_config.get("processor", {})
            dotted_path = process_definition.get("name")
            if dotted_path is not None:
                processor = load_plugin("process", process_definition)
                match processor:
                    case BasePrefectProcessor():
                        print(f"Deploying process {process_id!r} with prefect...")
                        processor.deploy_as_prefect_flow(
                            queue_name=prefect_queue_name,
                            deployment_name=deployment_name,
                            storage_block_name=storage_block_name,
                            storage_sub_path=storage_sub_path,
                        )
                    case _:
                        print(
                            f"Process {process_id!r} is not deployable with "
                            f"prefect, skipping..."
                        )
            else:
                raise click.BadParameter("Invalid pygeoapi configuration")
        else:
            raise click.BadParameter(
                f"{process_id!r} is not a valid pygeoapi 'process'")
