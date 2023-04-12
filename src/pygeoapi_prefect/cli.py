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
def deploy_process(
        process_id: str,
        pygeoapi_config: Path,
):
    """Create and apply prefect deployment for PROCESS_ID.

    Configure deployment parameters for the process in pygeoapi's configuration file."""
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
                        try:
                            deployment_config = process_definition.get(
                                "prefect", {})["deployment"]
                            deployment_name = deployment_config["name"]
                            prefect_queue_name = deployment_config.get("queue", "test")
                            storage_block_name = deployment_config.get("storage-block")
                            storage_sub_path = deployment_config.get("storage-path")
                        except KeyError:
                            raise click.Abort(
                                "Deployment not specified in pygeoapi config file")
                        else:
                            print(f"Deploying process {process_id!r} with prefect...")
                            processor.deploy_as_prefect_flow(
                                deployment_name=deployment_name,
                                queue_name=prefect_queue_name,
                                storage_block_name=storage_block_name,
                                storage_sub_path=storage_sub_path,
                            )
                            print("Done!")
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
