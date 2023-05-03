from contextlib import nullcontext as does_not_raise
from unittest import mock

import pytest

from pygeoapi_prefect import util


@pytest.mark.parametrize(
    "extended_name, expectation",
    [
        pytest.param("remote-file-system/something", does_not_raise()),
        pytest.param("something-else/something", pytest.raises(RuntimeError)),
    ],
)
def test_get_storage_file_system(extended_name, expectation):
    with (
        mock.patch("pygeoapi_prefect.util.prefect.filesystems") as mock_fs,
        expectation,
    ):
        mock_fs.RemoteFileSystem.load.return_value = mock.sentinel.something
        result = util.get_storage_file_system(extended_name)
        mock_fs.RemoteFileSystem.load.assert_called_once_with(
            extended_name.partition("/")[-1]
        )
        assert result is mock.sentinel.something
