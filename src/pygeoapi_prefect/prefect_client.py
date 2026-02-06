import uuid

from prefect.client.orchestration import get_client
from prefect.client.schemas import FlowRun
from prefect.server.schemas import filters
from prefect.server.schemas.core import Flow
from prefect.server.schemas.states import StateType


async def list_flow_runs(
        states: list[StateType] | None = None, name_like: str | None = None
) -> list[FlowRun]:
    """Retrieve existing prefect flow_runs, optionally filtered by state and name"""
    if states is not None:
        state_filter = filters.FlowRunFilterState(
            type=filters.FlowRunFilterStateType(any_=states)
        )
    else:
        state_filter = None
    if name_like is not None:
        name_like_filter = filters.FlowRunFilterName(like_=name_like)
    else:
        name_like_filter = None
    async with get_client() as client:
        response = await client.read_flow_runs(
            flow_run_filter=filters.FlowRunFilter(
                state=state_filter,
                name=name_like_filter,
            )
        )
    return response


async def get_flow_run(flow_run_name: str) -> tuple[FlowRun, Flow] | None:
    """Retrieve prefect flow_run details."""
    async with get_client() as client:
        flow_runs = await client.read_flow_runs(
            flow_run_filter=filters.FlowRunFilter(
                name=filters.FlowRunFilterName(any_=[flow_run_name])
            )
        )
        try:
            flow_run = flow_runs[0]
        except IndexError:
            result = None
        else:
            prefect_flow = await client.read_flow(flow_run.flow_id)
            result = flow_run, prefect_flow
        return result


async def get_flow(flow_id: uuid.UUID) -> Flow:
    """Retrive prefect flow details."""
    async with get_client() as client:
        return await client.read_flow(flow_id)
