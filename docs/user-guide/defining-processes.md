# Processes

Pygeoapi-prefect can be used to run pygeoapi processes of two different kinds:

- [Standard pygeoapi processes](#running-standard-pygeoapi-processes)
- [Custom prefect-powered processes](#running-prefect-powered-processes)


## Running standard pygeoapi processes

Pre-existing pygeoapi processes can simply be run by the `pygeoapi-prefect` pygeoapi process manager without any
modification.

When using this option it is not possible to take advantage of most prefect features. Processes are always run
locally, and it is not possible to use prefect features other than its ephemeral API and the UI for monitoring
execution of processes. Other prefect features such as deployments and result storage are not available.

Nevertheless, you can [launch prefect server](prefect.md) and enjoy monitoring solution for the execution of
pygeoapi processes just by using the prefect UI.


## Running prefect-powered processes

In order to take full advantage of pygeoapi-prefect you will need to use its custom process class as a base
for your own processes.

Prefect-based processes are able to use all prefect features such as blocks, deployments, scheduling, etc.

As such, in order to use prefect-powered processes you will need to:

1. [Write the code that performs the computation as a prefect flow](#implement-process-as-a-prefect-flow)
2. [Define a pygeoapi processor class](#define-pygeoapi-processor-class)
3. [Enable the processor in pygeoapi configuration file](#enable-process-in-pygeoapi)
4. [Ensure you have prefect running](prefect.md)
5. [Deploy your flow](deployments.md)


### Implement process as a prefect flow

!!! note

    We recommend getting having the [prefect docs](https://docs.prefect.io/latest/) at hand when defining new flows.


pygeoapi-prefect is able to use regular prefect flows. However, they must meet the following requirements:

1. The `@flow()` decorator must at least include the `persist_results=True` parameter;

2. Flows **must** accept the following parameters, which are passed to it by the pygeoapi process manager:

    - `job_id: str` - The pygeoapi job id, as generated by its process manager

    - `result_storage_block: str` - the extended name (_i.e._ `<block-type-slug>/<block-name>`) of a prefect block that
      is to be used for storing whatever outputs are to be generated during execution

    - `process_description: ProcessDescription` - The details about the processor, as known by pygeoapi

    - `execution_request: ExecuteRequest` - Execution-related details about the current pygeoapi job to be used in the
      flow run

3. Flows must store whatever results they produce using a prefect storage block

4. Flows must return an instance of `pygeoapi.models.processes.JobStatusInfoInternal`


A simple example:

```python
from prefect import flow, get_run_logger
from prefect.blocks.core import Block
from prefect.filesystems import LocalFileSystem
from pygeoapi.models import processes as schemas
from pygeoapi.process import exceptions


@flow(persist_result=True)
def simple_flow(
        job_id: str,
        result_storage_block: str | None,
        process_description: schemas.ProcessDescription,
        execution_request: schemas.ExecuteRequest
) -> schemas.JobStatusInfoInternal:
  """This is a simple prefect flow.

  It complies with pygeoapi-prefect's requirements, namely:

  - The @flow decorator includes `persist_results=True`
  - Accepts the required input parameters (job_id, result_storage_block,
    process_description, execution_request)
  - Stores outputs using prefect block
  - Returns a status_info
  """
  logger = get_run_logger()
  logger.debug("Starting execution...")

  # 1. retrieve inputs
  # 1.1. some may be mandatory
  try:
    name = execution_request.inputs["name"].__root__
  except KeyError:
    raise exceptions.MissingJobParameterError("Cannot process without a name")
  else:
    # 1.2. others may be optional
    msg = execution_request.inputs.get("message")
    message = msg.__root__ if msg is not None else ""

    # 2. determine where results will be stored
    if result_storage_block is not None:
      storage = Block.load(result_storage_block)
    else:
      storage = LocalFileSystem()

    # 3. Get to work! - Perform the generation of outputs
    result_value = f"Hello {name}! {message}".strip()

    # 4. Store the generated outputs using a prefect block
    result_path = f"{job_id}/output-result.txt"
    storage.write_path(result_path, result_value.encode("utf-8"))

    # 5. Return a status info object
    return schemas.JobStatusInfoInternal(
      jobID=job_id,
      processID=process_description.id,
      status=schemas.JobStatus.successful,
      generated_outputs={
        "result": schemas.OutputExecutionResultInternal(
          location=f"{storage.basepath}/{result_path}",
          media_type=(
            process_description.outputs["result"].schema_.content_media_type
          ),
        )
      },
    )
```


### Define pygeoapi processor class

In order to be usable by pygeoapi-prefect, the prefect flow defined above needs to be wrapped
up in a custom pygeoapi processor. This processor must:

- Derive from `BasePrefectProcessor` - This custom base class provides prefect-related
  functionality

- Have the `process_flow` class variable. This is a reference to the prefect flow function which is
  used for doing the work. See the previous section on how to implement a suitable flow.

- Have the `process_description` class variable, which holds metadata useful for pygeoapi to be able
  to describe the process. This must be an instance of `ProcessDescription`.
  It is a description of the process, including its inputs as outputs. The only major requirement
  here is that the description's `id` property needs to match the name of the process, as
  specified in the pygeoapi configuration file

A simple example, meant to work together with [the prefect flow defined earlier](#implement-process-as-a-prefect-flow):

!!! warning

    Inside your custom processor modules be sure to use absolute imports. Otherwise the prefect deployment may not be
    able to find all of your code's dependencies.


```python
from prefect import flow
from pygeoapi.models import processes as schemas
from pygeoapi_prefect.process.base import BasePrefectProcessor

@flow(persist_result=True)
def simple_flow(
        job_id: str,
        result_storage_block: str | None,
        process_description: schemas.ProcessDescription,
        execution_request: schemas.ExecuteRequest
) -> schemas.JobStatusInfoInternal:
    ...  # omitted for brevity, see above for the full implementation


class SimpleFlowProcessor(BasePrefectProcessor):
    process_flow = simple_flow
    process_description = schemas.ProcessDescription(
        id="simple-flow",  # id MUST match key given in pygeoapi config
        version="0.0.1",
        title="Simple flow Processor",
        jobControlOptions=[
            schemas.ProcessJobControlOption.SYNC_EXECUTE,
            schemas.ProcessJobControlOption.ASYNC_EXECUTE
        ],
        inputs={
            "name": schemas.ProcessInput(
                title="Name",
                schema=schemas.ProcessIOSchema(type=schemas.ProcessIOType.STRING)
            ),
            "message": schemas.ProcessInput(
                title="Message",
                schema=schemas.ProcessIOSchema(type=schemas.ProcessIOType.STRING),
                minOccurs=0
            ),
        },
        outputs={
            "result": schemas.ProcessOutput(
                schema=schemas.ProcessIOSchema(type=schemas.ProcessIOType.STRING, contentMediaType="text/plain")
            )
        },
    )
```


# Enable process in pygeoapi

In order to be usable, a process must be specified in pygeoapi configuration file. pygeoapi-prefect
recognizes the following process-related configuration:

`processor.name`
: Dotted path to the pygeoapi processor class to be used

`processor.prefect.result_storage`
: Identifier of the prefect storage block that is to be used for storing generated outputs. Flow runs must always
  use a storage block to store execution outputs

`processor.prefect.deployment.name`
: Name of the prefect deployment that will be created/used

`processor.prefect.deployment.queue`
: Name of the prefect queue where flow runs will be scheduled to

`processor.prefect.deployment.storage_block`
: Identifier of the prefect storage block that is to be used for storing the flow deployment

`processor.prefect.deployment.storage_sub_path`
: Path for storing the flow deployment


A simple example:

```yaml
# pygeoapi configuration file

resources:

  # id of the process MUST be the same as the `id` property of the processor's
  # `process_description`
  hi-prefect-world:
    type: process
    processor:
      name: pygeoapi_prefect.examples.hi_prefect_world.HiPrefectWorldProcessor
      prefect:
        result_storage: remote-file-system/test-sb1-results
        deployment:
          name: minio
          queue: pygeoapi
          storage_block: remote-file-system/test-sb1
          storage_sub_path: hi-prefect-world-flow
```
