"""Sample prefect-powered pygeoapi process and utilities.

This module contains:

- The `hi_prefect_world` flow, which is where the actual processing takes place

- The `deploy_flow` function, which can be used to deploy the prefect flow

- The `HiPrefectWorldProcessor`, which is a pygeoapi process definition that can be used
  in conjunction with the prefect process manager
"""
import logging

from prefect import flow

from pygeoapi_prefect import schemas
from pygeoapi_prefect.process.base import BasePrefectProcessor

LOGGER = logging.getLogger(__name__)

RESULT_OUTPUT_MEDIA_TYPE = "application/json"


@flow(
    flow_run_name="pygeoapi-job-{pygeoapi_job_id}"
)
def hi_prefect_world(
        pygeoapi_job_id: str, name: str, message: str | None = None
) -> tuple[str, dict[str, str]]:
    """Echo back a greeting message."""
    LOGGER.warning(f"Inside the hi_prefect_world flow - locals: {locals()}")
    result = f"Hi from prefect {name}{f' - {message}' if message is not None else ''}"
    return RESULT_OUTPUT_MEDIA_TYPE, {"result": result}


class HiPrefectWorldProcessor(BasePrefectProcessor):
    process_flow = hi_prefect_world

    process_metadata = schemas.Process(
        id="hi-prefect-world",  # id MUST match the key given in pygeoapi config for the process
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
                keywords=["cool-name"]
            ),
            "message": schemas.ProcessInput(
                schema=schemas.ProcessIOSchema(type=schemas.ProcessIOType.STRING),
                title="Message",
                description="An optional additional message to be echoed to the world",
                minOccurs=0,
                maxOccurs=1,
            )
        },
        outputs={
            "result": schemas.ProcessOutput(
                schema=schemas.ProcessIOSchema(
                    type=schemas.ProcessIOType.OBJECT,
                    contentMediaType=RESULT_OUTPUT_MEDIA_TYPE
                )
            )
        },
        links=[],
        keywords=[
            "process",
            "hi-world",
            "example"
        ],
        example={"inputs": {"message": "wazzaaaap!"}}
    )
