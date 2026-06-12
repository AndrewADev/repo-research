"""AG-UI streaming endpoint.

Bridges CopilotKit / `@ag-ui/client` to the existing LangGraph agent. The
request body is the canonical `ag_ui.core.RunAgentInput`; the response is an
AG-UI SSE stream produced by reusing `agui.emit_agui_events` and serialized with
`ag_ui.encoder.EventEncoder` (the same `data: {json}\n\n` wire format the client
expects). Thread persistence reuses the project's `AsyncSqliteSaver` pattern, so
runs are checkpointed exactly like the CLI.
"""

from collections.abc import AsyncIterator

from ag_ui.core import RunAgentInput, RunErrorEvent
from ag_ui.encoder import EventEncoder
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from agui import emit_agui_events
from api.schemas import coerce_text
from integrations.github.agent import close_agent_resources, create_configured_agent
from integrations.github.models import get_empty_state
from storage import default_db_path, open_async_sqlite_saver

router = APIRouter()


def _latest_user_text(payload: RunAgentInput) -> str:
    """Extract the newest user turn.

    The agent is checkpointed by ``thread_id``, so only the latest user message
    is fed in; prior history is restored from the checkpoint (mirroring the CLI's
    ``run_prompt``).
    """
    for message in reversed(payload.messages):
        if getattr(message, "role", None) == "user":
            return coerce_text(getattr(message, "content", ""))
    if payload.messages:
        return coerce_text(getattr(payload.messages[-1], "content", ""))
    return ""


async def _encode_stream(payload: RunAgentInput, db_path: str) -> AsyncIterator[str]:
    encoder = EventEncoder()
    graph = create_configured_agent()
    state = get_empty_state(messages=[HumanMessage(content=_latest_user_text(payload))])
    config: RunnableConfig = {"configurable": {"thread_id": payload.thread_id}}
    try:
        async with open_async_sqlite_saver(db_path) as saver:
            graph.checkpointer = saver
            try:
                async for event in emit_agui_events(graph, state, config):
                    if isinstance(event, RunErrorEvent):
                        # raw_event holds the original Exception for in-process
                        # callers; it is not JSON-serializable on the wire.
                        event.raw_event = None
                    yield encoder.encode(event)
            finally:
                graph.checkpointer = None
    finally:
        close_agent_resources(graph)


@router.post("/agent")
async def run_agent(payload: RunAgentInput) -> StreamingResponse:
    """Run the agent for one turn and stream AG-UI events as SSE."""
    return StreamingResponse(
        _encode_stream(payload, default_db_path()),
        media_type="text/event-stream",
    )
