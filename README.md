# pygeoapi-prefect

A process manager for [pygeoapi] that uses [prefect].


[pygeoapi]: https://pygeoapi.io/
[prefect]: https://www.prefect.io/


This project implements a pygeoapi process manager that uses prefect. It enables you to:

1. Run standard pygeoapi processes as prefect flow runs.

   Pre-existing processes can simply be run by the `pygeoapi-prefect` pygeoapi process manager without any 
   modification. Using this option processes are always run locally and it is not possible to use prefect features
   other than its ephemeral API and the UI for monitoring execution of processes. Other prefect features such as
   deployments, storage, blocks 

2. Define your pygeoapi processes as prefect flows and take full advantage of prefect features like deployments


## Development

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

Now stand up pygeoapi with the provided config files:

```shell
PYGEOAPI_CONFIG=example-config.yml PYGEOAPI_OPENAPI=example-openapi.yml poetry run pygeoapi serve
```

If you need to regenerate the openapi description file, run:

```shell
poetry run pygeoapi openapi generate example-config.yml > example-openapi.yml
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
