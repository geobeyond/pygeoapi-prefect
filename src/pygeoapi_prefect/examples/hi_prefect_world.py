"""Sample prefect-powered pygeoapi process and utilities.

This module contains:

- The `hi_prefect_world` flow, which is where the actual processing takes place

- The `deploy_flow` function, which can be used to deploy the prefect flow

- The `HiPrefectWorldProcessor`, which is a pygeoapi process definition that can be used
  in conjunction with the prefect process manager
"""
import logging

import pygeoapi.models.processes as schemas
from prefect import flow
from prefect.filesystems import (
    LocalFileSystem,
    RemoteFileSystem,
)
from prefect.context import FlowRunContext
from pygeoapi.process import exceptions

# don't perform relative imports because otherwise prefect deployment won't
# work properly
from pygeoapi_prefect.process.base import BasePrefectProcessor

logger = logging.getLogger(__name__)


@flow(persist_result=True)
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
    logger.warning(f"Inside the hi_prefect_world flow - locals: {locals()}")
    try:
        name = execution_request.inputs["name"].__root__
    except KeyError:
        raise exceptions.MissingJobParameterError("Cannot process without a name")
    else:
        msg = execution_request.inputs.get("message")
        if result_storage_block is not None:
            storage_block_type, storage_base_path = result_storage_block.partition("/")[
                ::2
            ]
            if storage_block_type == "remote-file-system":
                file_system = RemoteFileSystem.load(storage_base_path)
            else:
                raise RuntimeError(
                    f"File systems of type {storage_block_type!r} are not supported "
                    f"by this process"
                )
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


@flow()
def new_hi(
    execution_request: schemas.ExecuteRequest,
    chosen_execution_mode: schemas.ProcessExecutionMode,
    process_description: schemas.ProcessDescription,
) -> schemas.JobStatusInfoInternal:
    """Echo back a greeting message."""
    flow_run_ctx = FlowRunContext.get()
    name = execution_request.inputs["name"].__root__
    msg = (
        m.__root__ if (m := execution_request.inputs.get("message")) is not None else ""
    )
    result_echo = f"Hi from prefect {name}. {msg}".strip()
    # what to return?
    # - could return JobStatusInfoInternal, but then we'd need to store
    #   results inside the flow and ignore prefect's results and storage,
    #   which seems silly.
    # - Could return just the result and let prefect store the result by setting
    #   persist_results in the flow. This means result can be stored in some
    #   remote storage block too. How would pygeoapi handle that? I guess the
    #   job manager could deal with generating the status_info and could also
    # deal with the fetching of results
    status_info = schemas.JobStatusInfoInternal(
        jobID=str(flow_run_ctx.flow_run.id),
        processID=process_description.id,
        status=schemas.JobStatus.successful,
        message="process completed successfully",
        created=flow_run_ctx.start_time,
        started=flow_run_ctx.flow_run.start_time,
        finished=flow_run_ctx.flow_run.end_time,
        updated=flow_run_ctx.flow_run.end_time,
        progress=100,
        negotiated_execution_mode=chosen_execution_mode,
        requested_response_type=execution_request.response,
        requested_outputs=execution_request.outputs,
        generated_outputs={
            "result": schemas.OutputExecutionResultInternal(
                location="",
                media_type=(
                    process_description.outputs["result"].schema_.content_media_type
                ),
            )
        },
    )
    return status_info


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
