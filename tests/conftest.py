import pytest
from prefect.testing.utilities import prefect_test_harness


@pytest.fixture(scope="session")
def prefect_fixture():
    with prefect_test_harness():
        yield
