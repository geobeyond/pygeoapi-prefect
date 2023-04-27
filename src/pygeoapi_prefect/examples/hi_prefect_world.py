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
from prefect.context import FlowRunContext

# don't perform relative imports because otherwise prefect deployment won't
# work properly
from pygeoapi_prefect.process.base import BasePrefectProcessor

logger = logging.getLogger(__name__)

RESULT_OUTPUT_MEDIA_TYPE = "application/json"


@flow(flow_run_name="pygeoapi-job-{pygeoapi_job_id}")
def hi_prefect_world(
    pygeoapi_job_id: str, name: str, message: str | None = None
) -> tuple[str, dict[str, str]]:
    """Echo back a greeting message."""
    logger.warning(f"Inside the hi_prefect_world flow - locals: {locals()}")
    result = f"Hi from prefect {name}{f' - {message}' if message is not None else ''}"
    return RESULT_OUTPUT_MEDIA_TYPE, {"result": result}


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


@flow()
def another_hi(execution_request: schemas.ExecuteRequest) -> dict[str, str]:
    """Echo back a greeting message."""
    logger.debug(f"Inside the flow - locals: {locals()}")
    name = execution_request.inputs["name"].__root__
    msg = m.__root__ if (m := execution_request.inputs["message"]) is not None else ""
    return {"echo": f"Hi from prefect {name}. {msg}".strip()}


class HiPrefectWorldProcessor(BasePrefectProcessor):
    process_flow = hi_prefect_world

    process_description = schemas.ProcessDescription(
        id="hi-prefect-world",  # id MUST match key given in pygeoapi config
        version="0.0.1",
        title={"en": "Hi prefect world Processor"},
        description={"en": "An example processor that is created with pydantic"},
        jobControlOptions=[
            schemas.ProcessJobControlOption.SYNC_EXECUTE,
            schemas.ProcessJobControlOption.ASYNC_EXECUTE,
        ],
        outputTransmission=[schemas.ProcessOutputTransmissionMode.VALUE],
        inputs={
            "name": schemas.ProcessInput(
                schema=schemas.ProcessIOSchema(type=schemas.ProcessIOType.STRING),
                minOccurs=1,
                maxOccurs=1,
                title="Name",
                description="Some name you think is cool. It will be echoed back.",
                keywords=["cool-name"],
            ),
            "message": schemas.ProcessInput(
                schema=schemas.ProcessIOSchema(type=schemas.ProcessIOType.STRING),
                title="Message",
                description="An optional additional message to be echoed to the world",
                minOccurs=0,
                maxOccurs=1,
            ),
        },
        outputs={
            "result": schemas.ProcessOutput(
                schema=schemas.ProcessIOSchema(
                    type=schemas.ProcessIOType.OBJECT,
                    contentMediaType=RESULT_OUTPUT_MEDIA_TYPE,
                )
            )
        },
        links=[],
        keywords=["process", "hi-world", "example"],
        example={"inputs": {"message": "wazzaaaap!"}},
    )
