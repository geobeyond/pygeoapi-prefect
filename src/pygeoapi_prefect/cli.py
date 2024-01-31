from pathlib import Path

import click
from prefect.blocks.core import Block
from prefect.deployments import Deployment
from prefect.filesystems import RemoteFileSystem
from pygeoapi.process.manager import get_manager
from pygeoapi.process.base import UnknownProcessError
from pygeoapi.util import yaml_load

from .process.base import BasePrefectProcessor


@click.group(name="prefect")
def root():
    """Commands provided by the pygeoapi-prefect package."""
    ...


@root.command()
@click.argument("block_name")
@click.argument("base_path")
@click.argument("endpoint_url")
@click.argument("key")
@click.argument("secret")
def create_remote_storage_block(
    block_name: str, base_path: str, endpoint_url: str, key: str, secret: str
):
    """Create storage block of type 'remote-file-system' on the prefect server

    PARAMETERS

    block_name - A name for the storage block. Note that it will then be referenced
    by prefect as 'remote-file-system/<block_name>'

    base_path - The base path for the storage block. This depends on the remote storage
    being used. As an example, with S3-compatible storage you can use
    's3://<bucket-name>'

    endpoint_url - Base URL of the remote storage. For example, a local minIO instance
    could use 'http://localhost:9000'

    key - User id of the remote storage

    secret - User password of the remote storage

    """
    print(f"Creating block remote-file-system/{block_name}...")
    block = RemoteFileSystem(
        basepath=base_path,
        settings={
            "key": key,
            "secret": secret,
            "client_kwargs": {"endpoint_url": endpoint_url},
        },
    )
    block.save(block_name, overwrite=True)
    print("Done!")


@root.command()
@click.argument("process_id")
@click.option(
    "-c",
    "--pygeoapi-config",
    type=Path,
    envvar="PYGEOAPI_CONFIG",
    help=(
        "pygeoapi configuration file path. This can also be specified "
        "by the PYGEOAPI_CONFIG environment variable"
    ),
)
def deploy_process(
    process_id: str,
    pygeoapi_config: Path,
):
    """Create and apply prefect deployment for PROCESS_ID.

    Configure deployment parameters for the process in pygeoapi's configuration
    file.
    """
    with pygeoapi_config.open() as fh:
        config = yaml_load(fh)
    manager = get_manager(config)
    try:
        processor = manager.get_processor(process_id)
    except UnknownProcessError as err:
        raise click.BadParameter(f"Process {process_id!r} not found") from err
    else:
        if isinstance(processor, BasePrefectProcessor):
            if processor.deployment_info is not None:
                print(f"Deploying process {process_id!r} with prefect...")
                if (sb := processor.deployment_info.storage_block) is not None:
                    storage = Block.load(sb)
                else:
                    storage = None
                deployment = Deployment.build_from_flow(
                    processor.process_flow,
                    name=processor.deployment_info.name,
                    work_queue_name=processor.deployment_info.queue,
                    storage=storage,
                    path=processor.deployment_info.storage_sub_path,
                )
                deployment.apply()
                print("Done!")
            else:
                raise click.Abort("Deployment not specified in pygeoapi config file")
        else:
            print(
                f"Process {process_id!r} is not deployable with "
                f"prefect, skipping..."
            )
