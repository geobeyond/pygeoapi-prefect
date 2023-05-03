"""Sample prefect-powered pygeoapi process and utilities.

This module contains:

- The `hi_prefect_world` flow, which is where the actual processing takes place

- The `deploy_flow` function, which can be used to deploy the prefect flow

- The `HiPrefectWorldProcessor`, which is a pygeoapi process definition that can be used
  in conjunction with the prefect process manager
"""
import pygeoapi.models.processes as schemas
from prefect import (
    flow,
    get_run_logger,
)
from prefect.filesystems import LocalFileSystem
from pygeoapi.process import exceptions

# don't perform relative imports because otherwise prefect deployment won't
# work properly
from pygeoapi_prefect.process.base import BasePrefectProcessor
from pygeoapi_prefect.util import get_storage_file_system


@flow(persist_result=True, log_prints=True)
def hi_prefect_world(
    job_id: str,
    result_storage_block: str | None,
    process_description: schemas.ProcessDescription,
    execution_request: schemas.ExecuteRequest,
) -> schemas.JobStatusInfoInternal:
    """Echo back a greeting message.

    Execution follows this pattern:

    - get inputs from the provided execution request
    - generate result
    - persist result
    - return JobStatusInfoInternal
    """
    logger = get_run_logger()
    logger.warning(f"Inside the hi_prefect_world flow - locals: {locals()}")
    try:
        name = execution_request.inputs["name"].__root__
    except KeyError:
        raise exceptions.MissingJobParameterError("Cannot process without a name")
    else:
        msg = execution_request.inputs.get("message")
        if result_storage_block is not None:
            file_system = get_storage_file_system(result_storage_block)
        else:
            file_system = LocalFileSystem()
        print(f"file_system: {file_system}")
        message = msg.__root__ if msg is not None else ""
        result_value = f"Hello {name}! {message}".strip()
        result_path = f"{job_id}/output-result.txt"
        file_system.write_path(result_path, result_value.encode("utf-8"))
    return schemas.JobStatusInfoInternal(
        jobID=job_id,
        processID=process_description.id,
        status=schemas.JobStatus.successful,
        generated_outputs={
            "result": schemas.OutputExecutionResultInternal(
                location=f"{file_system.basepath}/{result_path}",
                media_type=(
                    process_description.outputs["result"].schema_.content_media_type
                ),
            )
        },
    )


class HiPrefectWorldProcessor(BasePrefectProcessor):
    process_flow = hi_prefect_world

    process_description = schemas.ProcessDescription(
        id="hi-prefect-world",  # id MUST match key given in pygeoapi config
        version="0.0.1",
        title="Hi prefect world Processor",
        description="An example processor that is created with pydantic",
        jobControlOptions=[
            schemas.ProcessJobControlOption.SYNC_EXECUTE,
            schemas.ProcessJobControlOption.ASYNC_EXECUTE,
        ],
        inputs={
            "name": schemas.ProcessInput(
                title="Name",
                description="Some name you think is cool. It will be echoed back.",
                schema=schemas.ProcessIOSchema(type=schemas.ProcessIOType.STRING),
                keywords=["cool-name"],
            ),
            "message": schemas.ProcessInput(
                title="Message",
                description="An optional additional message to be echoed to the world",
                schema=schemas.ProcessIOSchema(type=schemas.ProcessIOType.STRING),
                minOccurs=0,
            ),
        },
        outputs={
            "result": schemas.ProcessOutput(
                schema=schemas.ProcessIOSchema(
                    type=schemas.ProcessIOType.STRING,
                    contentMediaType="text/plain",
                )
            )
        },
        keywords=[
            "process",
            "prefect",
            "example",
        ],
        example={"inputs": {"name": "spiderboy"}},
    )
