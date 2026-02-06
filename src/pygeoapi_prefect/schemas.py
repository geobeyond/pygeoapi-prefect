"""Schemas used internally by the process manager."""

import datetime as dt
import enum
from typing import Annotated, Any, Union

import pydantic

from pygeoapi.util import JobStatus


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


class ProcessExecutionMode(enum.Enum):
    sync_execute = "sync-execute"
    async_execute = "async-execute"


class RequestedProcessExecutionMode(enum.Enum):
    wait = "wait"
    respond_async = "respond-async"


class ProcessOutputTransmissionMode(enum.Enum):
    VALUE = "value"
    REFERENCE = "reference"


class ProcessResponseType(enum.Enum):
    document = "document"
    raw = "raw"


class ProcessJobControlOption(enum.Enum):
    SYNC_EXECUTE = "sync-execute"
    ASYNC_EXECUTE = "async-execute"
    DISMISS = "dismiss"


class ProcessIOType(enum.Enum):
    ARRAY = "array"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    NUMBER = "number"
    OBJECT = "object"
    STRING = "string"


class ProcessIOFormat(enum.Enum):
    # this is built from:
    # - the jsonschema spec at: https://json-schema.org/draft/2020-12/json-schema-validation.html#name-defined-formats  # noqa: E501
    # - the OAPI - Processes spec (table 13) at: https://docs.ogc.org/is/18-062r2/18-062r2.html#ogc_process_description  # noqa: E501
    DATE_TIME = "date-time"
    DATE = "date"
    TIME = "time"
    DURATION = "duration"
    EMAIL = "email"
    HOSTNAME = "hostname"
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    URI = "uri"
    URI_REFERENCE = "uri-reference"
    # left out `iri` and `iri-reference` as valid URIs are also valid IRIs
    UUID = "uuid"
    URI_TEMPLATE = "uri-template"
    JSON_POINTER = "json-pointer"
    RELATIVE_JSON_POINTER = "relative-json-pointer"
    REGEX = "regex"
    # the below `binary` entry does not seem to be defined in the jsonschema spec  # noqa: E501
    # nor in OAPI - Processes - but it is mentioned in OAPI - Processes spec as an example  # noqa: E501
    BINARY = "binary"
    GEOJSON_FEATURE_COLLECTION_URI = (
        "http://www.opengis.net/def/format/ogcapi-processes/0/"
        "geojson-feature-collection"
    )
    GEOJSON_FEATURE_URI = (
        "http://www.opengis.net/def/format/ogcapi-processes/0/geojson-feature"
    )
    GEOJSON_GEOMETRY_URI = (
        "http://www.opengis.net/def/format/ogcapi-processes/0/geojson-geometry"
    )
    OGC_BBOX_URI = "http://www.opengis.net/def/format/ogcapi-processes/0/ogc-bbox"
    GEOJSON_FEATURE_COLLECTION_SHORT_CODE = "geojson-feature-collection"
    GEOJSON_FEATURE_SHORT_CODE = "geojson-feature"
    GEOJSON_GEOMETRY_SHORT_CODE = "geojson-geometry"
    OGC_BBOX_SHORT_CODE = "ogc-bbox"


# this is a 'pydantification' of the schema.yml fragment, as shown
# on the OAPI - Processes spec
class ProcessIOSchema(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(use_enum_values=True)

    title: str | None = None
    multiple_of: Annotated[float | None, pydantic.Field(alias="multipleOf")] = None
    maximum: float | None = None
    exclusive_maximum: Annotated[bool | None, pydantic.Field(alias="exclusiveMaximum")] = False
    minimum: float | None = None
    exclusive_minimum: Annotated[bool | None, pydantic.Field(alias="exclusiveMinimum")] = False
    max_length: Annotated[int | None, pydantic.Field(ge=0, alias="maxLength")] = None
    min_length: Annotated[int, pydantic.Field(ge=0, alias="minLength")] = 0
    pattern: str | None = None
    max_items: Annotated[int | None, pydantic.Field(ge=0, alias="maxItems")] = None
    min_items: Annotated[int, pydantic.Field(ge=0, alias="minItems")] = 0
    unique_items: Annotated[bool | None, pydantic.Field(alias="uniqueItems")] = False
    max_properties: Annotated[int | None, pydantic.Field(ge=0, alias="maxProperties")] = None
    min_properties: Annotated[int, pydantic.Field(ge=0, alias="minProperties")] = 0
    required: list[str] | None = None
    enum: list[Any] | None = None
    type_: Annotated[ProcessIOType | None, pydantic.Field(alias="type")] = None
    not_: Annotated["ProcessIOSchema | None", pydantic.Field(alias="not")] = None
    allOf: list["ProcessIOSchema"] | None = None
    oneOf: list["ProcessIOSchema"] | None = None
    anyOf: list["ProcessIOSchema"] | None = None
    items: list["ProcessIOSchema"] | None = None
    properties: "ProcessIOSchema | None" = None
    additional_properties: Annotated[
        bool | "ProcessIOSchema" | None,
        pydantic.Field(alias="additionalProperties")
    ] = True
    description: str | None = None
    format_: Annotated[ProcessIOFormat | None, pydantic.Field(alias="format")] = None
    default: dict | None = None
    nullable: bool | None = False
    read_only: Annotated[bool | None, pydantic.Field(alias="readOnly")] = False
    write_only: Annotated[bool | None, pydantic.Field(alias="writeOnly")] = False
    example: dict | None = None
    deprecated: bool | None = False
    content_media_type: Annotated[str | None, pydantic.Field(alias="contentMediaType")] = None
    content_encoding: Annotated[str | None, pydantic.Field(alias="contentEncoding")] = None
    content_schema: Annotated[str | None, pydantic.Field(alias="contentSchema")] = None


class ProcessOutput(pydantic.BaseModel):
    title: str | None = None
    description: str | None = None
    schema_: Annotated[ProcessIOSchema, pydantic.Field(alias="schema")]


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


class ProcessSummary(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(use_enum_values=True)

    version: str
    id: str
    title: dict[str, str] | str | None = None
    description: dict[str, str] | str | None = None
    keywords: list[str] | None = None
    job_control_options: Annotated[
        list[ProcessJobControlOption] | None, pydantic.Field(alias="jobControlOptions")
    ] = [ProcessJobControlOption.SYNC_EXECUTE]
    output_transmission: Annotated[
        list[ProcessOutputTransmissionMode] | None, pydantic.Field(alias="outputTransmission")
    ] = [ProcessOutputTransmissionMode.VALUE]
    links: list[Link] | None = None


class ProcessDescription(ProcessSummary):
    inputs: dict[str, ProcessInput]
    outputs: dict[str, ProcessOutput]
    example: dict | None = None


class ExecutionInputBBox(pydantic.BaseModel):
    bbox: Annotated[list[float], pydantic.Field(min_length=4, max_length=4)]
    crs: str | None = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"


class ExecutionInputValueNoObjectArray(
    pydantic.RootModel[
        list[
            "ExecutionInputBBox" | int | str | "ExecutionInputValueNoObjectArray"
        ]
    ]
):
    pass


class ExecutionInputValueNoObject(
    pydantic.RootModel[
        str,
        float,
        int,
        bool,
        ExecutionInputBBox,
        ExecutionInputValueNoObjectArray,
    ]
):
    """Models the `inputValueNoObject.yml` schema defined in OAPIP."""

    pass


class ExecutionFormat(pydantic.BaseModel):
    """Models the `format.yml` schema defined in OAPIP."""

    media_type: Annotated[str | None, pydantic.Field(alias="mediaType")] = None
    encoding: str | None = None
    schema_: Annotated[str | dict | None, pydantic.Field(alias="schema")] = None


class ExecutionQualifiedInputValue(pydantic.BaseModel):
    """Models the `qualifiedInputValue.yml` schema defined in OAPIP."""

    value: Union[ExecutionInputValueNoObject, dict]
    format_: ExecutionFormat | None = None


class ExecutionOutput(pydantic.BaseModel):
    """Models the `output.yml` schema defined in OAPIP."""

    model_config = pydantic.ConfigDict(use_enum_values=True)

    format_: Annotated[ExecutionFormat | None, pydantic.Field(alias="format")] = None
    transmission_mode: Annotated[
        ProcessOutputTransmissionMode | None, pydantic.Field(alias="transmissionMode")
    ] = ProcessOutputTransmissionMode.VALUE.value


class ExecutionSubscriber(pydantic.BaseModel):
    """Models the `subscriber.yml` schema defined in OAPIP."""

    success_uri: Annotated[str, pydantic.Field(alias="successUri")]
    in_progress_uri: Annotated[str | None, pydantic.Field(alias="inProgressUri")] = None
    failed_uri: Annotated[str | None, pydantic.Field(alias="failedUri")] = None


class ExecuteRequest(pydantic.BaseModel):
    """Models the `execute.yml` schema defined in OAPIP."""

    model_config = pydantic.ConfigDict(use_enum_values=True)

    inputs: dict[
        str,
        Union[
            ExecutionInputValueNoObject,
            ExecutionQualifiedInputValue,
            Link,
            list[
                Union[
                    ExecutionInputValueNoObject,
                    ExecutionQualifiedInputValue,
                    Link,
                ]
            ],
        ],
    ] | None = None
    outputs: dict[str, ExecutionOutput] | None = None
    response: ProcessResponseType | None = ProcessResponseType.raw
    subscriber: ExecutionSubscriber | None = None


class OutputExecutionResultInternal(pydantic.BaseModel):
    location: str
    media_type: str


class ExecutionDocumentSingleOutput(
    pydantic.RootModel[Union[ExecutionInputValueNoObject, ExecutionQualifiedInputValue, Link]]
):
    pass


class ExecutionDocumentResult(pydantic.RootModel[dict[str, ExecutionDocumentSingleOutput]]):
    pass


class JobStatusInfoBase(pydantic.BaseModel):
    job_id: Annotated[str, pydantic.Field(alias="jobID")]
    process_id: Annotated[str | None, pydantic.Field(alias="processID")] = None
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
