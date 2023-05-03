from unittest import mock

import pytest
from click.testing import CliRunner

from pygeoapi_prefect import cli


@pytest.fixture
def cli_runner():
    yield CliRunner()


@pytest.fixture
def config():
    yield {}


@pytest.mark.parametrize(
    "block_name, base_path, endpoint_url, key, secret",
    [
        pytest.param(
            "some-name", "some-basepath", "some-endpoint-url", "some-key", "some-secret"
        )
    ],
)
def test_create_storage_block(
    cli_runner, block_name, base_path, endpoint_url, key, secret
):
    with mock.patch("pygeoapi_prefect.cli.RemoteFileSystem", autospec=True) as mock_fs:
        result = cli_runner.invoke(
            cli.create_storage_block, [block_name, base_path, endpoint_url, key, secret]
        )
        assert result.exit_code == 0
        mock_fs.assert_called_once_with(
            basepath=base_path,
            settings={
                "key": key,
                "secret": secret,
                "client_kwargs": {"endpoint_url": endpoint_url},
            },
        )
        mock_fs.return_value.save.assert_called_once_with(block_name, overwrite=True)


@pytest.mark.parametrize(
    "process_id, pygeoapi_config, expected_exit_code",
    [
        pytest.param(
            "hi-prefect",
            {
                "server": {
                    "manager": {
                        "name": "pygeoapi_prefect.manager.PrefectManager",
                    },
                },
                "resources": {
                    "hi-prefect": {
                        "type": "process",
                        "processor": {
                            "name": "pygeoapi_prefect.examples.hi_prefect_world.HiPrefectWorldProcessor",  # noqa: E501
                            "prefect": {
                                "deployment": {
                                    "name": "something",
                                    # "queue": "phony-queue",
                                    "storage_block": "some storage block",
                                }
                            },
                        },
                    },
                },
            },
            1,
            id="no queue provided",
        ),
        pytest.param(
            "hi-prefect",
            {
                "server": {
                    "manager": {
                        "name": "pygeoapi_prefect.manager.PrefectManager",
                    },
                },
                "resources": {
                    "hi-prefect": {
                        "type": "process",
                        "processor": {
                            "name": "pygeoapi_prefect.examples.hi_prefect_world.HiPrefectWorldProcessor",  # noqa: E501
                            "prefect": {
                                "deployment": {
                                    "name": "something",
                                    "queue": "phony-queue",
                                    "storage_block": "some storage block",
                                }
                            },
                        },
                    },
                },
            },
            0,
            id="successful execution",
        ),
        pytest.param(
            "hi-prefect",
            {
                "server": {
                    "manager": {
                        "name": "pygeoapi_prefect.manager.PrefectManager",
                    },
                },
                "resources": {
                    "hi-prefect": {
                        "type": "process",
                        "processor": {
                            "name": "pygeoapi_prefect.examples.hi_prefect_world.HiPrefectWorldProcessor",  # noqa: E501
                            "prefect": {},
                        },
                    },
                },
            },
            1,
            id="no deployment in config",
        ),
    ],
)
def test_deploy_process(cli_runner, process_id, pygeoapi_config, expected_exit_code):
    with (
        mock.patch("pygeoapi_prefect.cli.Path", autospec=True) as mock_path,
        mock.patch("pygeoapi_prefect.cli.yaml_load", autospec=True) as mock_yaml_load,
        mock.patch("pygeoapi_prefect.cli.Block", autospec=True) as mock_block,
        mock.patch("pygeoapi_prefect.cli.Deployment", autospec=True) as mock_deployment,
    ):
        mock_path.return_value.open.return_value = mock.sentinel.some_fake_fh
        mock_yaml_load.return_value = pygeoapi_config
        mock_block.load.return_value = mock.sentinel.some_fake_fs
        mock_deployment_instance = mock.MagicMock()
        mock_deployment.build_from_flow.return_value = mock_deployment_instance
        result = cli_runner.invoke(
            cli.deploy_process,
            [
                process_id,
                "--pygeoapi-config",
                __file__,
            ],
        )
        print(f"{result.exit_code=}")
        print(f"{result.stdout=}")
        print(f"{result.exception=}")
        assert result.exit_code == expected_exit_code
        if expected_exit_code == 0:
            mock_block.load.assert_called()
            mock_deployment_instance.apply.assert_called_once()
