# Docker example

#### Work pool

Prefect is able to run flows inside ephemeral docker containers.
This requires that a Prefect work pool be created with the `docker` type:

=== "uv"

    ```shell
    uv run prefect work-pool create --type docker my-pool
    ```

=== "pip"

    ```shell
    source .venv/bin/activate
    
    prefect work-pool create --type docker my-pool
    ```

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
from prefect import flow, task


@flow(log_prints=True)
def simple_flow(
        processor_id: str,
        pygeoapi_job_id: str,  # noqa, this is used for naming flow_runs
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
def generate_greeting(name: str, message: str | None = None) -> str:
    result = f"Hi {name}!"
    if message:
        result += f" {message}"
    return result


if __name__ == "__main__":
    simple_flow.deploy(
        name="first-deployment",
        work_pool_name="my-pool",
        image="pygeoapi-prefect/flows/simple-flow",
        push=False
    )
```

Deploy it:

=== "uv"

    ```shell
    uv run python simple_flow.py
    ```

=== "pip"

    ```shell
    python simple_flow.py
    ```

This creates a docker image named `pygeoapi-prefect/flows/simple-flow:{date}` with the flow contents and registers
a deployment named `simple-flow/first-deployment` with the Prefect server. Because our `simple_flow.deploy()` call
includes `push=False`, this docker image lives in the local filesystem only.

You can check the Prefect server UI in order to verify that your deployment is now registered. You can also used the
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
  simple-flow:
    type: process
    processor:
      prefect:
        deployment:
          name: simple-flow/first-deployment
          result_storage_key_template: "{parameters[pygeoapi_job_id]}.pickle"
        metadata:
          version: 0.0.1
          title: Hi world prefect example
          description: >
            An example processor that is powered by a Prefect deployment.
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

```shell
pygeoapi serve
```


#### Process execution via pygeoapi

Check that pygeoapi recognizes our Prefect flow:

```shell
http localhost:5000/processes/simple-flow
```

The response should include the description of the `simple-flow` processor and also a link for executing it. Execution
can be requested with:

```shell
curl \
    -sSi \
    -X POST "http://localhost:5000/processes/simple-flow/execution" \
    -H "Content-Type: application/json" \
    -d '{"inputs": {"name": "Joe"}}'
```

The response:

```shell
HTTP/1.1 201 CREATED
Content-Type: None
Content-Language: en-US
Preference-Applied: respond-async
Location: http://localhost:5000/jobs/af101d53-7dcc-4882-a15b-a85fd4381153

{"jobID":"af101d53-7dcc-4882-a15b-a85fd4381153","type":"process","status":"accepted"}
```
