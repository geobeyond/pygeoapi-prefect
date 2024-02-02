# Development

Install this project with poetry

```shell
git clone
poetry install --with dev
```

Start the prefect server:

```shell
poetry run prefect server start
```

Update the prefect config, as directed by the prefect server:

```shell
poetry run prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api
```

If you want to deploy a pygeoapi process locally with prefect, then also start a prefect agent:

```shell
poetry run prefect agent start --work-queue pygeoapi
```

Now stand up pygeoapi with the provided config files:

```shell
export PYGEOAPI_INSTALL_DIR=${HOME}/dev/pygeoapi
export PYGEOAPI_CONFIG=example-config.yml
export PYGEOAPI_OPENAPI=example-openapi.yml

poetry run uvicorn \
       --reload \
       --reload-dir=${PYGEOAPI_INSTALL_DIR} \
       --reload-dir=$(pwd) \
       --reload-include='*.py' \
       --reload-include='*.yml' \
       --host=0.0.0.0 \
       --port=5000 \
       --log-level=debug \
       --log-config=dev-log-config.yaml \
       pygeoapi.starlette_app:APP
```

!!! NOTE

    It is preferable to call `uvicorn` directly from the CLI over using `pygeoapi serve` as
    that will allow setting custom uvicorn flags, like the log config

If you need to regenerate the openapi description file, run:

```shell
poetry run pygeoapi openapi generate example-config.yml > example-openapi.yml
```

Deploy the `hi-prefect-world` process:

```shell
poetry run pygeoapi-prefect deploy-as-prefect-flow hi-prefect-world
```

- Run a deployed process with prefect

```shell
poetry run prefect deployment run --param
```


- List processes

  ```shell
  http -v localhost:5000/processes
  ```

- Execute the standard `hello-world` process via prefect:

  ```shell
  http -v localhost:5000/processes/hello-world/execution inputs:='{"message": "Yo", "name": "planet Earth"}'
  ```

- Execute our `hi-prefect-world` process:

  ```shell
  http -v localhost:5000/processes/hi-prefect-world/execution inputs:='{"message": "Yo", "name": "planet Earth"}'
  ```
