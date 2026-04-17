"""Schemas used internally by the process manager."""

import datetime as dt
import enum
from typing import (
    Annotated,
    Any,
    Literal,
    NewType,
)

import pydantic

from pygeoapi.util import (
    JobStatus,
    ProcessExecutionMode,
    RequestedResponse,
    Subscriber,
)

MediaType = NewType("MediaType", str)
ProcessId = NewType("ProcessId", str)
ResponseHeaders = NewType("ResponseHeaders", dict[str, str])
JobOutputs = str | dict | list | bytes


class PygeoapiPrefectJobId(str):
    FLOW_RUN_NAME_PREFIX = "pygeoapi_job_"

    def to_flow_run_name(self) -> str:
        return f"{self.FLOW_RUN_NAME_PREFIX}{self}"

    @classmethod
    def from_flow_run_name(cls, flow_run_name: str) -> "PygeoapiPrefectJobId":
        return cls(flow_run_name.replace(cls.FLOW_RUN_NAME_PREFIX, ""))


class PrefectDeployment(pydantic.BaseModel):
    name: str
    result_storage_block: str | None = None
    result_storage_key_template: str
    queue: str | None = None


class Link(pydantic.BaseModel):
    href: str
    rel: str
    type_: Annotated[str | None, pydantic.Field(alias="type")] = None
    title: str | None = None
    href_lang: Annotated[str | None, pydantic.Field(alias="hreflang")] = None

    def as_link_header(self) -> str:
        result = f"<{self.href}>"
        for field_name, field_info in self.__class__.model_fields.items():
            if field_name == "href":
                continue
            if (value := getattr(self, field_name, None)) is not None:
                fragment = f'{field_info.alias or field_name}="{value}"'
                result = "; ".join((result, fragment))
        return result


class ProcessOutputTransmissionMode(str, enum.Enum):
    VALUE = "value"
    REFERENCE = "reference"


class ProcessResponseType(str, enum.Enum):
    document = "document"
    raw = "raw"


class ProcessJobControlOption(str, enum.Enum):
    SYNC_EXECUTE = "sync-execute"
    ASYNC_EXECUTE = "async-execute"
    DISMISS = "dismiss"


class ProcessOutput(pydantic.BaseModel):
    title: str | None = None
    description: str | None = None
    # schema_: Annotated[ProcessIOSchema, pydantic.Field(alias="schema")]
    schema_: Annotated[dict[str, Any], pydantic.Field(alias="schema")]


class ProcessMetadata(pydantic.BaseModel):
    title: str | None = None
    role: str | None = None
    href: str | None = None


class AdditionalProcessIOParameters(ProcessMetadata):
    name: str
    value: list[str | float | int | list[dict] | dict]


class ProcessInput(ProcessOutput):
    keywords: list[str] | None = None
    metadata: list[ProcessMetadata] | None = None
    min_occurs: Annotated[int, pydantic.Field(alias="minOccurs")] = 1
    max_occurs: Annotated[int | str | None, pydantic.Field(alias="maxOccurs")] = 1
    additional_parameters: AdditionalProcessIOParameters | None = None


JobControlOptions = Annotated[
    list[ProcessJobControlOption], pydantic.Field(alias="jobControlOptions")
]


class InternalProcessDescription(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(use_enum_values=True)

    version: str
    title: dict[str, str] | str | None = None
    description: dict[str, str] | str | None = None
    keywords: list[str] | None = None
    # prefect-enabled processors can always run in either sync or async fashion
    job_control_options: JobControlOptions = [
        ProcessJobControlOption.SYNC_EXECUTE,
        ProcessJobControlOption.ASYNC_EXECUTE,
    ]
    output_transmission: Annotated[
        list[ProcessOutputTransmissionMode] | None,
        pydantic.Field(serialization_alias="outputTransmission"),
    ] = [ProcessOutputTransmissionMode.VALUE]
    links: list[Link] | None = None
    inputs: dict[str, ProcessInput]
    outputs: dict[str, ProcessOutput]
    example: dict | None = None


class ExecutionFormat(pydantic.BaseModel):
    """Models the `format.yml` schema defined in OAPIP."""

    media_type: Annotated[str | None, pydantic.Field(alias="mediaType")] = None
    encoding: str | None = None
    schema_: Annotated[str | dict | None, pydantic.Field(alias="schema")] = None


class ExecutionOutput(pydantic.BaseModel):
    """Models the `output.yml` schema defined in OAPIP."""

    model_config = pydantic.ConfigDict(use_enum_values=True)

    format_: Annotated[ExecutionFormat | None, pydantic.Field(alias="format")] = None
    transmission_mode: Annotated[
        ProcessOutputTransmissionMode | None, pydantic.Field(alias="transmissionMode")
    ] = ProcessOutputTransmissionMode.VALUE


class ExecutionSubscriber(pydantic.BaseModel):
    """Models the `subscriber.yml` schema defined in OAPIP."""

    success_uri: Annotated[str, pydantic.Field(alias="successUri")]
    in_progress_uri: Annotated[str | None, pydantic.Field(alias="inProgressUri")] = None
    failed_uri: Annotated[str | None, pydantic.Field(alias="failedUri")] = None


class ExecuteRequest(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(use_enum_values=True)
    inputs: dict[str, Any] | None = None
    outputs: dict[str, ExecutionOutput] | None = None
    response: RequestedResponse | None = RequestedResponse.raw
    subscriber: Subscriber | None = None
    deployment_info: PrefectDeployment


class OutputExecutionResultInternal(pydantic.BaseModel):
    location: str
    media_type: str


class JobStatusInfo(pydantic.BaseModel):
    processor_metadata: dict
    type_: Annotated[Literal["process"], pydantic.Field(serialization_alias="type")] = (
        "process"
    )
    job_id: Annotated[str, pydantic.Field(serialization_alias="jobID")]
    status: JobStatus
    message: str | None = None
    execution_parameters: dict[str, Any] | None = None
    created: dt.datetime | None = None
    started: dt.datetime | None = None
    finished: dt.datetime | None = None
    updated: dt.datetime | None = None
    progress: Annotated[int | None, pydantic.Field(ge=0, le=100)] = None

    def to_pygeoapi(self) -> dict[str, Any]:
        output_media_types = [
            out["schema"].get("contentMediaType", "application/octet-stream")
            for out_id, out in self.processor_metadata.get("outputs", {}).items()
        ]
        return {
            "created": self.created,
            "finished": self.finished,
            "identifier": self.job_id,
            "message": self.message,
            "mimetype": output_media_types[
                0
            ],  # pygeoapi only supports a single output per processor
            "parameters": self.execution_parameters,
            "process_id": self.processor_metadata["id"],
            "progress": self.progress,
            "started": self.started,
            "status": self.status.name,
            "type": self.type_,
            "updated": self.updated,
        }


class JobStatusInfoBase(pydantic.BaseModel):
    job_id: Annotated[str, pydantic.Field(serialization_alias="jobID")]
    process_id: Annotated[
        str | None, pydantic.Field(serialization_alias="processID")
    ] = None
    status: JobStatus
    message: str | None = None
    created: dt.datetime | None = None
    started: dt.datetime | None = None
    finished: dt.datetime | None = None
    updated: dt.datetime | None = None
    progress: Annotated[int | None, pydantic.Field(ge=0, le=100)] = None


class JobStatusInfoInternal(JobStatusInfoBase):
    negotiated_execution_mode: ProcessExecutionMode | None = None
    requested_response_type: ProcessResponseType | None = None
    requested_outputs: dict[str, ExecutionOutput] | None = None
    generated_outputs: dict[str, OutputExecutionResultInternal] | None = None


class JobList(pydantic.BaseModel):
    jobs: list[JobStatusInfo]
    number_matched: Annotated[int, pydantic.Field(serialization_alias="numberMatched")]

    def to_pygeoapi(self) -> dict[str, list[dict] | int]:
        """Return a suitable list of jobs for being processed by pygeoapi."""
        return {
            "jobs": [ji.to_pygeoapi() for ji in self.jobs],
            "numberMatched": self.number_matched,
        }
