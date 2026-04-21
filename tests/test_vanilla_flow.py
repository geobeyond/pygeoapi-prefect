import pytest

from pygeoapi_prefect import vanilla_flow


@pytest.mark.parametrize(
    "processor_id, expected", [pytest.param("some-id", "pygeoapi-some-id-local")]
)
def test_get_deployment_name(processor_id: str, expected: str):
    result = vanilla_flow.get_deployment_name(processor_id)
    assert result


def test_generate_flow_run_name(prefect_fixture):
    result = vanilla_flow.generate_flow_run_name()
    assert result == "pygeoapi_job_unknown"
