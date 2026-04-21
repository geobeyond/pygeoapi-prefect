# Development

## Installation

Install this project with uv

```shell
git clone
uv sync
```


## Set-up

Prepare a `.env` suitable for development, similar to:

```dotenv
# prefect variables
PREFECT_API_URL=http://127.0.0.1:4200/api
PREFECT_RESULTS_PERSIST_BY_DEFAULT=true
PREFECT_SERVER_ANALYTICS_ENABLED=false
DO_NOT_TRACK=1

# pygeoapi variables
PYGEOAPI_CONFIG=example-config.yml
PYGEOAPI_OPENAPI=example-openapi.yml
```

!!! WARNING

    We recommend naming the env file `pygeoapi-prefect.env` and sourcing it like this:

    ```shell
    set -o allexport; source pygeoapi-prefect.env; set +o allexport
    ```

    All following examples assume the env file has already been sourced.


Start the prefect server:

```shell
uv run prefect server start
```

The prefect UI shall now be available at http://localhost:4200


If you want to deploy a pygeoapi process locally with prefect, then also start a prefect worker. Here we specify a
worker of type `process` (i.e. flow runs execute locally, by spawning aditional Python processes) which consumes from
a pool named `pygeoapi`:

```shell
uv run prefect worker start --type process --pool pygeoapi
```

Now stand up pygeoapi

```shell
uv run pygeoapi serve --starlette
```

Deploy the `hi-prefect-world` process:

```shell
uv run pygeoapi-prefect deploy-as-prefect-flow hi-prefect-world
```

- Run a deployed process with prefect

```shell
uv run prefect deployment run --param
```


## Operations


!!! TIP

    All examples below use:

    - [httpie](https://httpie.io/) as a CLI HTTP client;
    - [jq](https://jqlang.org/) as a CLI JSON processor;


-  List available process ids

    ```shell
    http localhost:5000/processes | jq '.processes[].id'
    ```

-  Retrieve details about a process (for example the process with id `hello-world`):

    ```shell
    http localhost:5000/processes/hello-world | jq '.'
    ```

-  Execute the pygeoapi `hello-world` process, via prefect. In this example we pass a JSON object
   with the inputs that the process needs:

    ```shell
    http localhost:5000/processes/hello-world/execution \
        inputs:='{"message": "Yo", "name": "planet Earth"}'
    ```

    Prefect records flow run executions - you can check them in the Prefect UI, under `runs`

-  Execute our `hi-prefect-world` process:

    ```shell
    http -v localhost:5000/processes/hi-prefect-world/execution \
        inputs:='{"message": "Yo", "name": "planet Earth"}'
    ```
