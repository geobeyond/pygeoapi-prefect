from prefect import Flow
from pygeoapi.process.base import BaseProcessor

from .. import schemas


class BasePrefectProcessor(BaseProcessor):
    process_flow: Flow
    process_metadata: schemas.Process

    def __init__(self, name):
        super().__init__(
            {"name": name},
            self.process_metadata.dict(
                by_alias=True, exclude_none=True, exclude_unset=True)
        )

    def execute(self) -> tuple[str, dict[str, str]]:
        """Execute process.

        When implementing processes as prefect flows be sure to also use the
        pygeoapi-prefect process manager. The pygeoapi-prefect process manager will
        never call this method - it will call a process' prefect flow function instead.
        """
        raise NotImplementedError
