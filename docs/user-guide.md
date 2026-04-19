---
hide:
  - navigation
---

# User guide

## Installation

In time, this will be on the [Python Package Index]() but for now you need to use the
repository url to get it:

=== "uv"

    ```shell
    uv add https://github.com/geobeyond/pygeoapi-prefect --branch main
    ```

=== "pip"

    ```shell
    # create a virtualenv
    python3 -m venv .venv

    # activate it
    source .venv/bin/activate

    # perform installation
    pip install https://github.com/geobeyond/pygeoapi-prefect@main
    ```


## Set up

In order to work with pygeoapi-prefect, you need to set up:

- a Prefect server;
- pygeoapi;
- (if you want to support async execution) at least one Prefect worker.


### Prefect server

In order to use this project you need to have access to a running and appropriately configured Prefect server.
As the most basic setup, generate an env file for configuring Prefect, ensuring that you
enable [persistence of results](https://docs.prefect.io/v3/advanced/results).

```shell
cat << EOF > prefect-server.env
PREFECT_API_URL=http://127.0.0.1:4200/api
PREFECT_RESULTS_PERSIST_BY_DEFAULT=true
EOF
```

Then start a local Prefect server

=== "uv"

    ```shell
    # export the variables defined in the prefect-server.env file
    set -o allexport; source prefect-env.env; set +o allexport

    uv run prefect server start
    ```

=== "pip"

    ```shell
    # export the variables defined in the prefect-server.env file
    set -o allexport; source prefect-env.env; set +o allexport

    prefect server start
    ```

   This will start up a local Prefect server listening on port 4200. The Prefect UI becomes available at
   `http://localhost:4200`

Prefect is a very flexible platform and can be set up and configured in many ways. The only hard requirement 
for pygeoapi-prefect is that Prefect's result management facilities are enabled. Please consult the 
[Prefect documentation](https://docs.prefect.io/v3/get-started) and the [examples section](docker-example.md) for 
further configuration info.


### Pygeoapi

Enable the Prefect job/process manager by modifying your pygeoapi configuration file. The
`server.manager.name` configuration parameter needs to be set to `pygeopai_prefect.PrefectManager`.

```yaml
# pygeoapi configuration file
server:
  manager:
    name: pygeoapi_prefect.PrefectManager
```

#### Pygeoapi Prefect manager configuration

The Prefect Manager accepts the following configuration parameters, all of which are optional.
These should be specified as properties of the `server.manager` object:

-   `enable_async_job_execution: bool = True` - Whether to allow executing jobs in async mode. This is enabled by
    default and is the recommended way to operate. Async execution defers the scheduling of processor jobs to the
    Prefect scheduler, which can have its concurrency levels configured in a way that prevents overloading the server.

-   `enable_sync_job_execution: bool = False` - Whether to allow executing jobs in sync mode.

    If needed, the configuration of each processor is allowed to override this setting, making it possible to
    selectively enable sync execution for those processors in which it is a useful execution mode - see below for
    more details on this

    !!! WARNING

        This setting is disabled by default and we recommend keeping it disabled - Executing synchronously risks
        overloading the server in case a large number of requests is received.

- `sync_job_execution_timeout_seconds: int = 60` - How much time to give a sync job to finish its
  processing before declaring it as failed


#### Processors

In addition to the manager, you must configure pygeoapi with some resources of type `process`.
`PrefectManager` is able to work both with vanilla pygeoapi processors and with a custom Prefect-aware
processor type.


##### Vanilla pygeoapi processors

Vanilla pygeoapi processors (_i.e._ those that inherit from `pygeoapi.process.base.BaseProcessor`) can be used without
any modification. As usual, processes need to be specified in the pygeoapi configuration file. Example:

```yaml
# pygeoapi configuration file
resources:
  hello-world:
    type: process
    processor:
      name: HelloWorld
```

The `PrefectManager` wraps these processors inside a Prefect [flow](https://docs.prefect.io/v3/concepts/flows) and
is able to execute them by generating Prefect flow runs whenever an execution request is received. Execution can be
either sync or async, as both types are supported by the Prefect manager.


##### custom prefect-aware processors

If you prefer, you can write Prefect flows, deploy them using any of the multiple techniques supported by Prefect
and then adapt them to run as pygeoapi processors.

In order to be runnable via pygeoapi, your flows need to:

1.  Implement the [protocol](https://typing.python.org/en/latest/spec/protocol.html)
    defined in `pygeoapi_prefect.PygeoapiPrefectFlowProtocol`:

    ```python
    from typing import Protocol

    class PygeoapiPrefectFlowProtocol(Protocol):
        def __call__(
            self,
            processor_id: str,
            pygeoapi_job_id: str,
            inputs: dict,
            outputs: dict | None = None,
        ) -> None: ...
    ```
  
2.  The flow must have at least one Prefect task, which is where the processing output is be generated. This task 
    must return the generated output, which enables it to be managed by 
    [Prefect's result management facilities](https://docs.prefect.io/v3/advanced/results). This means this 
    result-generating task must:

    -   Be configured to persist results;
    -   Be configured with a result storage key that uses the pygeoapi job id - this is needed in order to ensure 
        pygeoapi is able to reconstruct the result's storage key for retrieval;
    -   The generated output must be a two-element tuple where the first element is the media type and the second 
        element is the actual output.

3.  The flow must already have been deployed in your Prefect environment. You can use any of the Prefect deployment 
    types (local processes, docker containers, k8s, etc.). Check the [examples](docker-example.md) section for more information

4.  Your pygeoapi configuration for the process needs to include a `prefect` section, with `deployment` and `metadata` 
    sub-sections.

This means that a very minimal flow looks like this:

```python
from prefect import flow, task

@flow()
def my_custom_flow(
    processor_id: str, 
    pygeoapi_job_id: str, 
    inputs: dict,
    outputs: dict | None = None
) -> None:
     # perform whatever preparatory steps
     generate_result(pygeoapi_job_id)


@task(
    persist_result=True,
    result_storage_key="{parameters[pygeoapi_job_id].pickle}",
    log_prints=True
)
def generate_result(pygeoapi_job_id: str) -> tuple[str, bytes]:
    return "text/plain", "Hi there, I am a result".encode()

```


##### Controlling processor execution modes via pygeoapi config

By default, pygeoapi does not allow modifying a processor's metadata in its configuration and assumes that
all parameters are to be set together with the processor code. This has the disadvantage of making it
impossible to toggle a processor's support for sync execution on and off without modifying the source code.

In order to ease configuration, `PrefectManager` looks for a `job_control_options` configuration key on
its the pygeoapi configuration file, which has the same meaning as the `jobControlOptions` metadata
key, _i.e._ it should be a list of strings with at least one entry and can contain `sync-execute` and
`async-execute` entries.

In the following example we disable sync mode in the manager but re-enable it in the `hello-world`
processor configuration:

```yaml
# pygeoapi configuration file
server:
  manager:
    name: pygeoapi_prefect.PrefectManager
    enable_sync_job_execution: false
resources:
  hello-world:
    type: process
    processor:
      name: HelloWorld
      job_control_options:
        - sync-execute
```


#### Launching pygeoapi

When starting pygeoapi, ensure the `PREFECT_API_URL` environment variable is set. As the most basic
launch of pygeoapi, you can create a `pygeoapi.env` file with these contents:

```shell

cat << EOF > pygeoapi.env
PYGEOAPI_CONFIG=<your-pygeoapi-config.file>
PYGEOAPI_OPENAPI=<your-pygeoapi-openapi.file>
PREFECT_API_URL=http://127.0.0.1:4200/api
EOF
```

And then launch pygeoapi:

=== "uv"

    ```shell
    # export the variables defined in the pygeoapi.env file
    set -o allexport; source pygeoapi.env; set +o allexport

    uv run pygeoapi serve
    ```

=== "pip"

    ```shell
    # export the variables defined in the pygeoapi.env file
    set -o allexport; source pygeoapi.env; set +o allexport

    pygeoapi serve
    ```

This will start the pygeoapi server, with `PrefectManager` as its process/job manager, and
using the Prefect server that is specified by the `PREFECT_API_URL` environment variable.


### Prefect worker(s)

When responding to requests that specify async execution mode, `PrefectManager` uses
[Prefect deployments]. These rely on an additional piece of
infrastructure, the Prefect worker, which means you also need to have at least a Prefect
worker up and running. There are many ways to set up a Prefect worker, depending on the chosen
execution model.

#### Run pygeoapi processors locally

For running pygeoapi processors locally, you can call a custom CLI command to start the worker:

=== "uv"

```shell
uv run pygeoapi plugins prefect deploy-local
```

=== "pip"

```shell
pygeoapi plugins prefect deploy-local
```

This will collect all processors defined in the pygeoapi configuration file that do not have a `prefect` options key,
create a Prefect static deployment for each and launch a Prefect worker that spawns new processes whenever it
receives a request for running a process.


#### Other execution models

Prefect is a very flexible platform and is able to coordinate the execution of processes in different
environments, such as remote hosts, docker containers, k8s pods, etc. In order to take advantage of these
other execution models, you will need to:

1. Configure your Prefect-related infrastructure
2. Deploy your processor code using [Prefect deployments]
3. Create pygeoapi processors that inherit from the custom pygeoapi-prefect `BasePrefectProcessor` and
  set them up accordingly in the pygeoapi configuration


[Prefect deployments]: https://docs.prefect.io/v3/concepts/deployments


!!! NOTE

    The `PrefectManager` only interacts with the Prefect server and with the Prefect result storage. This means
    that as long as you define a Prefect Flow and are able to deploy it, then it



## Usage


### Execute processes by making OGC API - Processes requests

??? tip "pygeoapi configuration"

    These examples use the below pygeoapi configuration. Notably:

    - `pygeoapi_prefect.PrefectManager` is set as the process/job manager
    - async execution mode is enabled (it is the default)
    - sync execution mode is disabled (it is the default)
    - the `hello-world` process is one of the standard pygeoapi processes. This contains further configuration
      enabling it to be executed in both sync and async mode, thus overriding the global option set on the manager

    ```yaml
    server:
      bind:
        host: 0.0.0.0
        port: 5000
      url: http://localhost:5000
      mimetype: application/json; charset=UTF-8
      encoding: utf-8
      gzip: false
      languages:
        - en-US
      # cors: true
      pretty_print: true
      limit: 10
      map:
        url: https://tile.openstreetmap.org/{z}/{x}/{y}.png
        attribution: '&copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap contributors</a>'
      manager:
        name: pygeoapi_prefect.PrefectManager

    logging:
      level: DEBUG

    metadata:
      identification:
        title:
          en: pygeoapi default instance
        description:
          en: pygeoapi provides an API to geospatial data
        keywords:
          en:
            - geospatial
        keywords_type: theme
        terms_of_service: https://creativecommons.org/licenses/by/4.0/
        url: https://example.org
      license:
        name: CC-BY 4.0 license
        url: https://creativecommons.org/licenses/by/4.0/
      provider:
        name: Organization Name
        url: https://pygeoapi.io
      contact:
        name: Lastname, Firstname
        position: Position Title
        address: Mailing Address
        city: City
        stateorprovince: Administrative Area
        postalcode: Zip or Postal Code
        country: Country
        phone: +xx-xxx-xxx-xxxx
        fax: +xx-xxx-xxx-xxxx
        email: you@example.org
        url: Contact URL
        hours: Mo-Fr 08:00-17:00
        instructions: During hours of service. Off on weekends.
        role: pointOfContact

    resources:
      hello-world:
        type: process
        processor:
          name: HelloWorld
          job_control_options:
            - sync-execute
            - async-execute
    ```

#### 1.  Execute a process with the default execution mode

A simple request for execution of the `hello-world` processor looks like this:

```shell
curl \
    -sS \
    -i \
    -X POST "http://localhost:5000/processes/hello-world/execution" \
    -H "Content-Type: application/json" \
    -d '{"inputs": {"name": "Joe"}}'
```

The response should look like this (some response headers omitted for brevity):

```shell
HTTP/1.1 200 OK
Content-Type: application/json
Preference-Applied: wait
Location: http://localhost:5000/jobs/157136b1-354b-4dca-87de-c2a8eddd692d

{"id":"echo","value":"Hello Joe!"}
```

When both execution modes are enabled (as per the pygeoapi configuration file shown above), the Prefect manager
honors the OGC API - Processes standard, which mentions that sync mode should be used
([section 7.11.2.3 - Requirement 25, Condition C](https://docs.ogc.org/is/18-062r2/18-062r2.html#sc_execution_mode)).
This is reported by the presence of the `Preference-Applied: wait` response header and by the direct inclusion of
the generated outputs as the body of the response.


#### 2.  Explicitly request async execution mode

Including the `Prefer: respond-async` request header causes the Prefect manager to dispatch execution in async
mode (as long as apropriately configured, as shown above):

```shell
curl \
    -sS \
    -i \
    -X POST "http://localhost:5000/processes/hello-world/execution" \
    -H "Content-Type: application/json" \
    -H "Prefer: respond-async" \
    -d '{"inputs": {"name": "Joe"}}'
```

In this case, the response is immediate and includes:


#### 3. Explicitly request sync execution mode:

```shell
curl \
    -X POST \
    "http://localhost:5000/processes/hello-world/execution" \
    -H "Content-Type: application/json" \
    -H "Prefer: wait" \
    -d '{"inputs": {"name": "Joe"}}'
```


### Monitor jobs via pygeoapi


### Monitor execution via Prefect UI
