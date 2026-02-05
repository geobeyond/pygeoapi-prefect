# Development

Install this project with uv

```shell
git clone
uv sync --group dev
```

Start the prefect server:

```shell
uv run prefect server start
```

Update the prefect config, as directed by the prefect server:

```shell
uv run prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api
```

If you want to deploy a pygeoapi process locally with prefect, then also start a prefect agent:

```shell
uv run prefect agent start --work-queue pygeoapi
```

Now stand up pygeoapi with the provided config files:

```shell
PYGEOAPI_CONFIG=example-config.yml PYGEOAPI_OPENAPI=example-openapi.yml uv run pygeoapi serve
```

If you need to regenerate the openapi description file, run:

```shell
uv run pygeoapi openapi generate example-config.yml > example-openapi.yml
```

Deploy the `hi-prefect-world` process:

```shell
uv run pygeoapi-prefect deploy-as-prefect-flow hi-prefect-world
```

- Run a deployed process with prefect

```shell
uv run prefect deployment run --param
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
