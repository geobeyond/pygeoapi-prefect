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

After installation, you need to have a Prefect server running and to set some environment variables
so that the Prefect Manager is able to communicate with it.

As the most basic setup:

generate an env file for configuring Prefect, ensuring that you
enable [persistence of results](https://docs.prefect.io/v3/advanced/results).

```shell
cat << EOF > prefect-env.env
PREFECT_API_URL=http://127.0.0.1:4200/api
PREFECT_RESULTS_PERSIST_BY_DEFAULT=true
EOF
```

Then start a local Prefect server

=== "uv"

    ```shell
    uv run prefect server start
    ```

=== "pip"

    ```shell
    prefect server start
    ```

   This will start up a local Prefect server listening on port 4200. The Prefect UI becomes available at
   `http://localhost:4200`


### Pygeoapi

Enable the Prefect job/process manager by modifying your pygeoapi configuration file. The
`server.manager.name` configuration parameter needs to be set to `pygeopai_prefect.PrefectManager`.

```yaml
# pygeoapi configuration file
server:
  manager:
    name: pygeoapi_prefect.PrefectManager
```

#### Prefect manager configuration

The Prefect Manager accepts the following configuration parameters, all of which are optional.
These should be specified as properties of the `server.manager` object:

- `enable_sync_job_execution: bool = False` - Whether to accept execution requests that run synchronously.

    !!! NOTE

        This setting is disabled by default and we recommend keeping it disabled - Executing syncronously risks
        overloading the server in case a large number of requestes is received.

        If needed, the metadata of
        each processor is allowed to override this setting, making it possible to selectively enable sync
        execution for those processors in which it is a useful execution mode.

        #### Controlling processor execution modes via pygeoapi config

        By default, pygeoapi does not allow modying a processor's metadata in its configuration and assumes that
        all parameters are to be set together with the processor code. This has the disadvantage of making it
        impossible to toggle a processor's support for sync execution on and off without modifying the source code.
        In order to ease configuration, `PrefectManager` will look for a `job_control_options` configuration key on
        its own configuration file, which has the same meaning as the `jobControlOptions` metadata key, _i.e._ it
        should be a list of strings with at least one entry and can contain `sync-execute` and `async-execute` entries.

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


- `enable_async_job_execution: bool = True` - Whether to accept execution requests that run asynchronously.
  This is enabled by default and is the recommended way to operate. Async execution defers the scheduling of
  processor execution to the Prefect scheduler, allowing for more stable operation, as the scheduler can control
  when to execute jobs depending on the load. Similarly to the previous parameter, this can also be
  overridden on a per-processor basis.

-  `use_deployment_for_sync_requests: bool = False` - Whether to call native pygeoapi processors via the
   Prefect deployment interface or not. If this is enabled:

    - Jobs are executed via the Prefect worker, which you must have started beforehand (as mentioned below)
    - Jobs are coordinated by the Prefect scheduler, which means that they may not start immediately
    - Jobs are run in a different process than pygeoapi
    - This means that job execution is slower, as there is a temporal overhead that is introduced by
      the coordination that happens between the Prefect scheduler service and the Prefect worker

    If this is disabled (the default), then jobs are executed immediately and run in the same process as
    pygeoapi.

    Note that regardless of this being enabled or not, all pygeoapi processes execution requests are tracked by
    Prefect and can be monitored using the Prefect UI.

- `sync_job_execution_timeout_seconds: int = 60` - How much time to give a sync job to finish its
  processing before declaring it as failed


#### Processors

In addition to the manager, you must configure pygeoapi with some resources of type `process`.
`PrefectManager` is able to work both with vanilla pygeoapi processors and with a custom Prefect-aware
processor type.


##### pygeoapi vanilla processes

Vanilla pygeoapi processes (_i.e._ those that inherit from `pygeoapi.process.base.BaseProcessor`) can be used without
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


###### Sync execution

Whenever pygeoapi receives a sync processor execution request, such as:

```shell
curl \
    -X POST \
    "http://localhost:5000/processes/hello-world/execution" \
    -H "Content-Type: application/json" \
    -d '{"inputs": {"name": "Joe"}}'
```

This is turned into a Prefect flow run and is executed locally, in the same process as pygeoapi. In other words,
the pygeoapi processor is wrapped as a Prefect flow and is run by the Prefect manager, using regular function calls.

Being managed by Prefect, this means.


###### Async execution

When pygeoapi receives an async processor execution request, such as:

```shell
curl \
    -X POST \
    "http://localhost:5000/processes/hello-world/execution" \
    -H "Content-Type: application/json" \
    -H "Prefer: respond-async" \
    -d '{"inputs": {"name": "Joe"}}'
```

This is turned into a Prefect flow and is executed via the respective processor deployment


##### custom prefect-aware processes

If you prefer, you can write Prefect flows, deploy them using any of the multiple techniques supported by Prefect
and then adapt them to run as pygeoapi processors.

In order to do so, your Prefect flows need to implement the
[protocol](https://typing.python.org/en/latest/spec/protocol.html)
defined in `pygeoapi_prefect.PygeoapiPrefectFlowProtocol`

```python
from prefect import flow

@flow()
def my_custom_flow()

```


#### Launching pygeoapi

When starting pygeoapi, ensure the `PREFECT_API_URL` environment variable is set. As the most basic
launch of pygeoapi, you can create a `pygeoapi.env` file with these contents:

```shell
# contents of pygeoapi.env
PYGEOAPI_CONFIG=<your-pygeoapi-config.file>
PYGEOAPI_OPENAPI=<your-pygeoapi-openapi.file>
PREFECT_API_URL=http://127.0.0.1:4200/api
PREFECT_RESULTS_PERSIST_BY_DEFAULT=true
```

And then launch pygeoapi:

=== "uv"

    ```shell
    # set the contents of pygeoapi.env as environment variables
    set -o allexport; source pygeoapi.env; set +o allexport

    uv run pygeoapi serve
    ```

=== "pip"

    ```shell
    # set the contents of pygeoapi.env as environment variables
    set -o allexport; source pygeoapi.env; set +o allexport

    pygeoapi serve
    ```

This shall start the pygeoapi server, with an instance of `PrefectManager` as its process/job manager, and
using the Prefect server that is specified by the `PREFECT_API_URL` environment variable. It
can now be used with both vanilla pygeoapi processes and a new kind of Prefect-aware processors.


### Prefect worker(s)

The Prefect server dispatches execution to workers, which means you also need to have at least a Prefect
worker up and running. There are many ways to set up a Prefect worker, depending on the chosen
execution model.

#### Run pygeoapi vanilla processes locally

For running pygeoapi vanilla processors locally, you can call a custom CLI command to start the worker:

=== "uv"

```shell
uv run pygeoapi plugins prefect deploy-static
```

=== "pip"

```shell
pygeoapi plugins prefect deploy-static
```

This will collect all vanilla processes defined in the pygeoapi configuration file, create a Prefect static
deployment for each and launch a Prefect worker that spawns new processes whenever it receives a request for
running a process


#### Other execution models

Prefect is a very flexible platform and is able to coordinate the execution of processes in different
environments, such as remote hosts, docker containers, k8s pods, etc. In order to take advantage of these
other execution models you will need to both:

- Configure your infrastructure
- Deploy your processor code using [Prefect deployments](https://docs.prefect.io/v3/concepts/deployments)
- Create pygeoapi processes that inherit from the custom pygeoapi-prefect `BasePrefectProcessor` and
  set them up accordingly in the pygeoapi configuration


!!! NOTE

    The `PrefectManager` only interacts with the Prefect server and with the Prefect result storage. This means
    that as long as you define a Prefect Flow and are able to deploy it, then it



## Usage


### Execute process

### Monitor execution via Prefect UI
