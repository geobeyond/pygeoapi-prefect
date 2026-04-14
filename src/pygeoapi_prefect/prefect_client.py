import uuid

from prefect.client.orchestration import get_client
from prefect.client.schemas import FlowRun
from prefect.client.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterName,
    FlowRunFilterState,
    FlowRunFilterStateType,
)
from prefect.client.schemas.objects import (
    Flow,
    StateType,
)


def list_flow_runs(
    states: list[StateType] | None = None,
    name_like: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[FlowRun], int]:
    """Retrieve existing prefect flow_runs, optionally filtered by state and name"""
    print(f"{locals()=}")
    if states is not None:
        state_filter = FlowRunFilterState(type=FlowRunFilterStateType(any_=states))
    else:
        state_filter = None
    if name_like is not None:
        name_like_filter = FlowRunFilterName(like_=name_like)
    else:
        name_like_filter = None
    with get_client(sync_client=True) as client:
        flow_run_filter = FlowRunFilter(
            state=state_filter,
            name=name_like_filter,
        )
        flow_runs = client.read_flow_runs(
            flow_run_filter=flow_run_filter, limit=limit, offset=offset
        )
        total_matched = client.count_flow_runs(flow_run_filter=flow_run_filter)
    return flow_runs, total_matched


def get_flow_run(flow_run_name: str) -> tuple[FlowRun, Flow] | None:
    """Retrieve prefect flow_run details."""
    with get_client(sync_client=True) as client:
        flow_runs = client.read_flow_runs(
            flow_run_filter=FlowRunFilter(name=FlowRunFilterName(any_=[flow_run_name]))
        )
        try:
            flow_run = flow_runs[0]
        except IndexError:
            result = None
        else:
            prefect_flow = client.read_flow(flow_run.flow_id)
            result = flow_run, prefect_flow
        return result


def get_flow(flow_id: uuid.UUID) -> Flow:
    """Retrieve prefect flow details."""
    with get_client(sync_client=True) as client:
        return client.read_flow(flow_id)
