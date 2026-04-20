# Docker example

#### Work pool

Prefect is able to run flows inside ephemeral docker containers.
This requires that a Prefect work pool be created with the `docker` type and some additional configuration.

For this example we are running everything inside a single node, so we'll configure the work pool to bind mount a
local directory inside the ephemeral container and have Prefect store results inside this directory.

This configuration is done by getting the default job template, modifying it and then using it to create a work pool.

??? note "Obtaining the default template for docker work pools"

    The default template can be gotten by using the Prefect CLI:

    === "uv"

        ```shell
        uv run prefect work-pool get-default-base-job-template --type docker
        ```

    === "pip"

        ```shell
        prefect work-pool get-default-base-job-template --type docker
        ```


The configuration of the work pool needs to specify a default bind volume and this also needs to be set as env
variables in order to be picked up by Prefect at runtime.

Configuration of the volumes can be done by modifying the `variables.properties.volumes.default` key and the
environment variables can be set by modifying the `variables.properties.env.default` key:

```yaml
# relevant modifications to the job template file
# file: docker-pool-job-template.json
{
  "variables": {
    "properties": {
      "volumes": {
        "default": ["<prefect-storage-path-on-local-disk>:/storage"]
      },
      "env": {
        "default": {
          "PREFECT_RESULTS_PERSIST_BY_DEFAULT": "true",
          "PREFECT_LOCAL_STORAGE_PATH": "/storage"
        }
  }
}
```

!!! warning

    Ensure you use absolute paths for your volume binds, as Prefect won't perform any expansion of special
    charachters like `~`


After having prepared the job template file, create the Prefect work pool:


=== "uv"

    ```shell
    uv run prefect work-pool create \
        --type docker \
        --base-job-template docker-pool-job-template.json \
        my-pool
    ```

=== "pip"

    ```shell
    source .venv/bin/activate

    prefect work-pool create \
        --type docker \
        --base-job-template docker-pool-job-template.json \
        my-pool
    ```

!!! warning

    Ensure the `PREFECT_LOCAL_STORAGE_PATH` environment variable is not set when you start the worker, as otherwise
    the ephemeral docker containers that it spawns will inherit this variable, overriding the configuration set
    in the job template

After creation, the work pool can be examined via the Prefect UI or CLI.

Start a worker that consumes work from this newly-created pool

??? note "Install prefect-docker"

    In order to start a Prefect worker that executes flow runs in docker containers, you need to have the
    [prefect-docker](https://pypi.org/project/prefect-docker/) package installed.

    Add it with:

    === "uv"

        ```shell
        uv add prefect-docker
        ```

    === "pip"

        ```shell
        pip install prefect-docker
        ```

=== "uv"

    ```shell
    uv run prefect worker start --pool my-pool
    ```

=== "pip"

    ```shell
    prefect worker start --pool my-pool
    ```


#### Flow deployment

Write your processing flow, for example:

```python
# simple_flow_docker.py
from prefect import flow, task


@flow(log_prints=True)
def simple_flow(
        processor_id: str,
        pygeoapi_job_id: str,
        inputs: dict,
        outputs: dict | None = None,
) -> None:
    print(f"Hi from simple_flow locals: {locals()}")
    generate_greeting(name=inputs["name"], message=inputs.get("message"))


@task(
    persist_result=True,
    result_storage_key="{parameters[pygeoapi_job_id]}.pickle",
    log_prints=True,
)
def generate_greeting(name: str, pygeoapi_job_id: str, message: str | None = None) -> str:
    result = f"Hi {name}!"
    if message:
        result += f" {message}"
    return result


if __name__ == "__main__":
    simple_flow.deploy(
        name="second-deployment",
        work_pool_name="my-pool",
        image="pygeoapi-prefect/flows/simple-flow",
        push=False
    )
```

Deploy it:

=== "uv"

    ```shell
    uv run python simple_flow_docker.py
    ```

=== "pip"

    ```shell
    python simple_flow_docker.py
    ```

This creates a docker image named `pygeoapi-prefect/flows/simple-flow:{date}` with the flow contents and registers
a deployment named `simple-flow/second-deployment` with the Prefect server. Because our `simple_flow.deploy()` call
includes `push=False`, this docker image lives in the local filesystem only.

You can check the Prefect server UI in order to verify that your deployment is now registered. You can also use the
Prefect API:

=== "uv"

    ```shell
    uv run prefect deployment ls
    ```

=== "pip"

    ```shell
    prefect deployment ls
    ```


#### Pygeoapi processor configuration

Configure pygeoapi with this newly deployed flow:

```yaml
# snippet of pygeoapi configuration file
# (the rest of the configuration has been omitted for brevity)
resources:
  another-simple-flow:
    type: process
    processor:
      prefect:
        deployment:
          name: simple-flow/second-deployment
          result_storage_key_template: "{job_id}.pickle"
        metadata:
          version: 0.0.1
          title: Hi world prefect example
          description: >
            An example processor that is powered by a Prefect deployment and executes inside ephemeral docker containers.
          inputs:
            name:
              description: Some name you think is cool. It will be used to greet you
              schema:
                type: string
            message:
              title: My message
              description: An optional additional message to be echoed
              schema:
                type: string
              minOccurs: 0
          outputs:
            result:
              schema:
                type: string
                contentMediaType: text/plain
          example:
            inputs:
              name: Joe
```

Finally, start pygeoapi:

=== "uv"

```shell
uv run pygeoapi serve
```

=== "pip"

```shell
pygeoapi serve
```


#### Process execution via pygeoapi

Check that pygeoapi recognizes our Prefect flow:

```shell
curl http://localhost:5000/processes/another-simple-flow
```

The response should include the description of the `another-simple-flow` processor and also a link for executing it. Execution
can be requested with:

```shell
curl \
    -sSi \
    -X POST "http://localhost:5000/processes/another-simple-flow/execution" \
    -H "Content-Type: application/json" \
    -d '{"inputs": {"name": "Joe"}}'
```

The response:

```shell
HTTP/1.1 200 OK
Content-Type: text/plain
Preference-Applied: wait
Location: http://localhost:5000/jobs/e5e26d6d-ce80-479e-a23e-5d488c71df17

Hi Joe!
```


An async request would be instead:

```shell
curl \
    -sSi \
    -X POST "http://localhost:5000/processes/another-simple-flow/execution" \
    -H "Prefer: respond-async" \
    -H "Content-Type: application/json" \
    -d '{"inputs": {"name": "Joe"}}'
```

And the response:

```shell
HTTP/1.1 201 CREATED
Preference-Applied: respond-async
Location: http://localhost:5000/jobs/2d5852fc-ae9d-46a9-bd1c-8d1f8e6c7ef0

{"jobID":"2d5852fc-ae9d-46a9-bd1c-8d1f8e6c7ef0","type":"process","status":"accepted"}
```
