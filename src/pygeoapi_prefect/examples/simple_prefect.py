"""Example pygeoapi process"""

from prefect import (
    flow,
    get_run_logger,
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
    ProcessDescription,
    ProcessInput,
    ProcessJobControlOption,
    ProcessOutput,
    OutputExecutionResultInternal,
)
from pygeoapi_prefect.process.base import BasePrefectProcessor


# When defining a prefect flow that will be deployed by prefect to some
# infrastructure, be sure to specify persist_result=True - otherwise the
# pygeoapi process manager will not be able to work properly
@flow(
    persist_result=True,
    log_prints=True,
)
def simple_flow(
    job_id: str,
    result_storage_block: str | None,
    process_description: ProcessDescription,
    execution_request: ExecuteRequest,
) -> JobStatusInfoInternal:
    """Echo back a greeting message.

    This is a simple prefect flow that does not use any tasks.
    """
    logger = get_run_logger()
    logger.debug(f"Inside the hi_prefect_world flow - locals: {locals()}")
    try:
        name = execution_request.inputs["name"].__root__
    except KeyError:
        raise ProcessorExecuteError("Cannot process without a name")
    else:
        msg = execution_request.inputs.get("message")
        message = msg.__root__ if msg is not None else ""
        if result_storage_block is not None:
            file_system = Block.load(result_storage_block)
        else:
            file_system = LocalFileSystem()
        print(f"file_system: {file_system}")
        result_value = f"Hello {name}! {message}".strip()
        result_path = f"{job_id}/output-result.txt"
        file_system.write_path(result_path, result_value.encode("utf-8"))
        return JobStatusInfoInternal(
            jobID=job_id,
            processID=process_description.id,
            status=JobStatus.successful,
            generated_outputs={
                "result": OutputExecutionResultInternal(
                    location=f"{file_system.basepath}/{result_path}",
                    media_type=(
                        process_description.outputs["result"].schema_.content_media_type
                    ),
                )
            },
        )


class SimpleFlowProcessor(BasePrefectProcessor):
    process_flow = simple_flow

    process_description = ProcessDescription(
        id="simple-flow",  # id MUST match key given in pygeoapi config
        version="0.0.1",
        title="Simple flow Processor",
        description=(
            "An example processor that is powered by prefect and executes a simple flow"
        ),
        jobControlOptions=[
            ProcessJobControlOption.SYNC_EXECUTE,
            ProcessJobControlOption.ASYNC_EXECUTE,
        ],
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
