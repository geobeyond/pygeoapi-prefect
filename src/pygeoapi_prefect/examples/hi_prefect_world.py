"""Example pygeoapi process"""

from prefect import (
    Flow,
    flow,
    get_run_logger,
    task,
)
from prefect.blocks.core import Block
from prefect.filesystems import LocalFileSystem
from pygeoapi.process.base import ProcessorExecuteError
from pygeoapi.util import JobStatus

# don't perform relative imports because otherwise prefect deployments won't
# work properly
from pygeoapi_prefect.schemas import (
    ExecuteRequest,
    JobStatusInfoInternal,
    OutputExecutionResultInternal,
    InternalProcessDescription,
    ProcessInput,
    ProcessJobControlOption,
    ProcessOutput,
)
from pygeoapi_prefect.process import BasePrefectProcessor


@flow(
    persist_result=True,
    log_prints=True,
)
def hi_prefect_world(
    job_id: str,
    result_storage_block: str | None,
    process_description: InternalProcessDescription,
    execution_request: ExecuteRequest,
) -> JobStatusInfoInternal:
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
        raise ProcessorExecuteError("Cannot process without a name")
    else:
        msg = execution_request.inputs.get("message")
        message = msg.__root__ if msg is not None else ""
        result_value = generate_result.submit(name, message)
        stored_path_future = store_result.submit(
            result_value, job_id, result_storage_block
        )
        status_info_future = generate_status_info.submit(
            job_id,
            process_description.id,
            stored_path_future,
            process_description.outputs["result"].schema_.content_media_type,
        )
        return status_info_future.result()


@task
def generate_result(name: str, message: str) -> str:
    return f"Hello {name}! {message}".strip()


@task
def store_result(contents: str, job_id: str, storage_block: str | None) -> str:
    if storage_block is not None:
        file_system = Block.load(storage_block)
    else:
        file_system = LocalFileSystem()
    result_path = f"{job_id}/output-result.txt"
    file_system.write_path(result_path, contents.encode("utf-8"))
    return f"{file_system.basepath}/{result_path}"


@task
def generate_status_info(
    job_id: str, process_id: str, result_path: str, result_media_type: str
):
    return JobStatusInfoInternal(
        jobID=job_id,
        processID=process_id,
        status=JobStatus.successful,
        generated_outputs={
            "result": OutputExecutionResultInternal(
                location=result_path,
                media_type=result_media_type,
            )
        },
    )


class HiPrefectWorldProcessor(BasePrefectProcessor):
    process_flow = hi_prefect_world

    process_description = InternalProcessDescription(
        version="0.0.1",
        title="Hi prefect world Processor",
        description="An example processor that is powered by prefect",
        inputs={
            "name": ProcessInput(
                title="Name",
                description="Some name you think is cool. It will be echoed back.",
                schema={"type": "string"},
                keywords=["cool-name"],
            ),
            "message": ProcessInput(
                title="Message",
                description="An optional additional message to be echoed to the world",
                schema={"type": "string"},
                minOccurs=0,
            ),
        },
        outputs={
            "result": ProcessOutput(
                schema={
                    "type": "string",
                    "contentMediaType": "text/plain",
                },
            )
        },
        keywords=[
            "process",
            "prefect",
            "example",
        ],
        example={"inputs": {"name": "spiderboy"}},
    )
