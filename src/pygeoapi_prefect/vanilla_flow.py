"""Run a pygeoapi processor as a Prefect flow.

Note that this module cannot have any relative imports, as it is intended that
it be importable by the Prefect worker as a script.
"""
import os
from pathlib import Path
from typing import Any

from prefect import flow
from prefect.runtime import flow_run
from pygeoapi.process.manager.base import get_manager
from pygeoapi.util import yaml_load


def generate_flow_run_name():
    pygeoapi_job_id = (flow_run.parameters or {}).get("pygeoapi_job_id") or "unknown"
    return f"pygeoapi_job_{pygeoapi_job_id}"


@flow(persist_result=True, log_prints=True)
def run_vanilla_processor(
        processor_id: str,
        data_: dict,
        pygeoapi_job_id: str,  # noqa, this is used for naming flow_runs
        outputs: dict | None = None,
) -> tuple[str, Any]:
    config_path = Path(os.environ["PYGEOAPI_CONFIG"])
    with config_path.open() as fh:
        config = yaml_load(fh)
    manager = get_manager(config)
    processor = manager.get_processor(processor_id)
    processor_output_media_type, processor_output = processor.execute(data_, outputs)
    return processor_output_media_type, processor_output
