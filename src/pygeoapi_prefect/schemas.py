"""Schemas used internally by the process manager."""
import datetime as dt
import enum
import typing
from pathlib import Path

import pydantic
from pygeoapi.util import JobStatus


class Link(pydantic.BaseModel):
    media_type: str
    rel: str
    title: str
    href: str
    href_lang: str


class ProcessIOType(enum.Enum):
    ARRAY = "array"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    NUMBER = "number"
    OBJECT = "object"
    STRING = "string"


class ProcessIOFormat(enum.Enum):
    # this is built from:
    # - the jsonschema spec at: https://json-schema.org/draft/2020-12/json-schema-validation.html#name-defined-formats
    # - the OAPI - Processes spec (table 13) at: https://docs.ogc.org/is/18-062r2/18-062r2.html#ogc_process_description
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
    # the below `binary` entry does not seem to be defined in the jsonschema spec
    # nor in OAPI - Processes - but it is mentioned in OAPI - Processes spec as an example
    BINARY = "binary"
    GEOJSON_FEATURE_COLLECTION_URI = "http://www.opengis.net/def/format/ogcapi-processes/0/geojson-feature-collection"
    GEOJSON_FEATURE_URI = "http://www.opengis.net/def/format/ogcapi-processes/0/geojson-feature"
    GEOJSON_GEOMETRY_URI = "http://www.opengis.net/def/format/ogcapi-processes/0/geojson-geometry"
    OGC_BBOX_URI = "http://www.opengis.net/def/format/ogcapi-processes/0/ogc-bbox"
    GEOJSON_FEATURE_COLLECTION_SHORT_CODE = "geojson-feature-collection"
    GEOJSON_FEATURE_SHORT_CODE = "geojson-feature"
    GEOJSON_GEOMETRY_SHORT_CODE = "geojson-geometry"
    OGC_BBOX_SHORT_CODE = "ogc-bbox"


class ProcessJobControlOption(enum.Enum):
    SYNC_EXECUTE = "sync-execute"
    ASYNC_EXECUTE = "async-execute"
    DISMISS = "dismiss"


class ProcessOutputTransmissionMode(enum.Enum):
    VALUE = "value"
    REFERENCE = "reference"


class ProcessMetadata(pydantic.BaseModel):
    title: str | None
    role: str | None
    href: str | None


class AdditionalProcessIOParameters(ProcessMetadata):
    name: str
    value: list[str | float | int | list[dict] | dict]


# this is a 'pydantification' of the schema.yml fragment, as shown
# on the OAPI - Processes spec
class ProcessIOSchema(pydantic.BaseModel):
    title: str | None
    multiple_of: float | None = pydantic.Field(alias="multipleOf")
    maximum: float | None
    exclusive_maximum: bool = pydantic.Field(False, alias="exclusiveMaximum")
    minimum: float | None
    exclusive_minimum: bool = pydantic.Field(False, alias="exclusiveMinimum")
    max_length: int = pydantic.Field(None, ge=0, alias="maxLength")
    min_length: int = pydantic.Field(0, ge=0, alias="minLength")
    pattern: str | None
    max_items: int | None = pydantic.Field(None, ge=0, alias="maxItems")
    min_items: int = pydantic.Field(0, ge=0, alias="minItems")
    unique_items: bool = pydantic.Field(False, alias="uniqueItems")
    max_properties: int | None = pydantic.Field(None, ge=0, alias="maxProperties")
    min_properties: int = pydantic.Field(0, ge=0, alias="minProperties")
    required: pydantic.conlist(str, min_items=1, unique_items=True) | None
    enum: pydantic.conlist(typing.Any, min_items=1, unique_items=False) | None
    type_: ProcessIOType | None = pydantic.Field(None, alias="type")
    not_: typing.Optional["ProcessIOSchema"] = pydantic.Field(None, alias="not")
    allOf: list["ProcessIOSchema"] | None
    oneOf: list["ProcessIOSchema"] | None
    anyOf: list["ProcessIOSchema"] | None
    items: list["ProcessIOSchema"] | None
    properties: typing.Optional["ProcessIOSchema"]
    additional_properties: typing.Union[bool, "ProcessIOSchema"] = pydantic.Field(
        True, alias="additionalProperties")
    description: str | None
    format_: ProcessIOFormat | None = pydantic.Field(None, alias="format")
    default: pydantic.Json[dict] | None
    nullable: bool = False
    read_only: bool = pydantic.Field(False, alias="readOnly")
    write_only: bool = pydantic.Field(False, alias="writeOnly")
    example: pydantic.Json[dict] | None
    deprecated: bool = False
    content_media_type: str | None = pydantic.Field(None, alias="contentMediaType")
    content_encoding: str | None = pydantic.Field(None, alias="contentEncoding")
    content_schema: str | None = pydantic.Field(None, alias="contentSchema")

    class Config:
        use_enum_values = True


class ProcessOutput(pydantic.BaseModel):
    title: str | None
    description: str | None
    schema_: ProcessIOSchema = pydantic.Field(alias="schema")


class ProcessInput(ProcessOutput):
    keywords: list[str] | None
    metadata: list[ProcessMetadata] | None
    min_occurs: int = pydantic.Field(1, alias="minOccurs")
    max_occurs: int | typing.Literal["unbounded"] = pydantic.Field(1, alias="maxOccurs")
    additional_parameters: AdditionalProcessIOParameters | None


class Process(pydantic.BaseModel):
    title: dict[str, str]
    description: dict[str, str]
    keywords: list[str]
    version: str
    id: str
    job_control_options: list[ProcessJobControlOption] = pydantic.Field(
        alias="jobControlOptions")
    output_transmission: list[ProcessOutputTransmissionMode] = pydantic.Field(
        [ProcessOutputTransmissionMode.VALUE], alias="outputTransmission")
    links: list[Link]

    inputs: dict[str, ProcessInput]
    outputs: dict[str, ProcessOutput]
    example: typing.Optional[dict]


class Job(pydantic.BaseModel):
    # these properties are based on investigation of pygeoapi.process.manager.tinydb
    identifier: str
    process_id: str
    status: JobStatus
    location: Path
    mimetype: str
    # these properties are based on investigation of pygeoapi.api.API
    job_start_datetime: dt.datetime
    job_end_datetime: dt.datetime
    message: str
    progress: float
    # parameters: ?


class ProcessManagerConfig(pydantic.BaseModel):
    # this is taken from the schema definition of pygeoapi config
    name: str
    connection: str
    output_dir: str