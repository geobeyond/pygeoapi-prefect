"""Run a pygeoapi processor as a Prefect flow.

Note that this module cannot have any relative imports, as it is intended that
it be importable by the Prefect worker as a script.
"""
import os
from pathlib import Path

from prefect import (
    Flow,
    flow,
    task,
)
from prefect.runtime import flow_run
from pygeoapi.process.manager.base import get_manager
from pygeoapi.process.base import BaseProcessor
from pygeoapi.util import yaml_load


def get_processor_as_flow(processor: BaseProcessor) -> Flow:
    return run_vanilla_processor.with_options(
        name=processor.metadata["id"],
        version=processor.metadata.get("version"),
        flow_run_name=generate_flow_run_name,
        validate_parameters=True,
    )


def get_deployment_name(processor_id: str) -> str:
    return f"pygeoapi-{processor_id}-local"


def generate_flow_run_name():
    pygeoapi_job_id = (flow_run.parameters or {}).get("pygeoapi_job_id") or "unknown"
    return f"pygeoapi_job_{pygeoapi_job_id}"


@task(
    persist_result=True,
    result_storage_key="{parameters[pygeoapi_job_id]}.pickle",
    log_prints=True,
)
def execute_processor(
        processor_id: str,
        pygeoapi_job_id: str,  # noqa, this is used for naming flow_runs and storage results
        inputs: dict,
        outputs: dict | None = None,
):
    config_path = Path(os.environ["PYGEOAPI_CONFIG"])
    with config_path.open() as fh:
        config = yaml_load(fh)
    manager = get_manager(config)
    processor = manager.get_processor(processor_id)
    processor_output_media_type, processor_output = processor.execute(inputs, outputs)
    return processor_output_media_type, processor_output


@flow()
def run_vanilla_processor(
        processor_id: str,
        pygeoapi_job_id: str,  # noqa, this is used for naming flow_runs
        inputs: dict,
        outputs: dict | None = None,
) -> None:
    execute_processor(
        processor_id=processor_id,
        pygeoapi_job_id=pygeoapi_job_id,
        inputs=inputs,
        outputs=outputs,
    )
