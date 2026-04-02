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
- at least one Prefect worker.


### Prefect server

After installation, you need to have a Prefect server running and to set some environment variables 
so that the Prefect Manager is able to communicate with it.

As the most basic setup, just start a local Prefect server

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


##### custom prefect-aware processes

TBD

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