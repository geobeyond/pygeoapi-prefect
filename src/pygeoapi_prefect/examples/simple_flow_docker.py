from typing import cast
from prefect import flow
from prefect.assets import materialize
from prefect.results import (
    get_result_store,
    LocalFileSystem,
)


@flow(log_prints=True)
def simple_flow(
    processor_id: str,
    pygeoapi_job_id: str,  # noqa, this is used for naming flow_runs
    inputs: dict,
    outputs: dict | None = None,
) -> None:
    print(f"Hi from simple_flow locals: {locals()}")
    result_store = get_result_store()
    storage = cast(LocalFileSystem, result_store.result_storage)
    base_path = storage.basepath
    base_task = generate_greeting

    dynamic_task = generate_greeting.with_options(
        # need to get the path where the result will be saved
        assets=[f"file://{base_path}/{pygeoapi_job_id}.pickle"],
    )
    dynamic_task(
        name=inputs["name"],
        pygeoapi_job_id=pygeoapi_job_id,
        message=inputs.get("message"),
    )


@materialize(
    "file://pygeoapi_job_id.pickle",
    persist_result=True,
    result_storage_key="{parameters[pygeoapi_job_id]}.pickle",
    log_prints=True,
)
def generate_greeting(
    name: str,
    pygeoapi_job_id: str,  # noqa, this is used for naming flow_runs
    message: str | None = None,
) -> tuple[str, bytes]:
    result = f"Hi {name}!"
    if message:
        result += f" {message}"
    return "text/plain", result.encode()


if __name__ == "__main__":
    simple_flow.deploy(
        name="second-deployment",
        work_pool_name="my-pool",
        image="pygeoapi-prefect/flows/simple-flow",
        push=False,
    )
