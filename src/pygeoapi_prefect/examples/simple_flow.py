from prefect import flow, task


@flow(log_prints=True)
def simple_flow(
        processor_id: str,
        pygeoapi_job_id: str,  # noqa, this is used for naming flow_runs
        inputs: dict,
        outputs: dict | None = None,
) -> None:
    print(f"Hi from simple_flow locals: {locals()}")
    generate_greeting(
        name=inputs["name"],
        pygeoapi_job_id=pygeoapi_job_id,
        message=inputs.get("message"),
    )


@task(
    persist_result=True,
    result_storage_key="{parameters[pygeoapi_job_id]}.pickle",
    log_prints=True,
)
def generate_greeting(
        name: str,
        pygeoapi_job_id: str,  # noqa, this is used for naming flow_runs
        message: str | None = None
) -> tuple[str, bytes]:
    result = f"Hi {name}!"
    if message:
        result += f" {message}"
    return "text/plain", result.encode()


if __name__ == "__main__":
    simple_flow.serve(
        name="first-deployment",
    )
