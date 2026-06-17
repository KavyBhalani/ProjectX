from langgraph.graph import StateGraph, END
from app.agents.state import CompanionState
from app.agents.nodes import (
    retrieve_context_node,
    pre_moderation_node,
    generate_response_node
)

def build_graph():
    workflow = StateGraph(CompanionState)

    workflow.add_node("retrieve_context", retrieve_context_node)
    workflow.add_node("pre_moderation", pre_moderation_node)
    workflow.add_node("generate_response", generate_response_node)

    workflow.set_entry_point("pre_moderation")

    def route_moderation(state: CompanionState) -> str:
        if not state.get("is_safe", True):
            return "generate_response"
        return "retrieve_context"

    workflow.add_conditional_edges("pre_moderation", route_moderation)
    workflow.add_edge("retrieve_context", "generate_response")
    
    # We end after generating the response.
    # Memory extraction will be triggered asynchronously via asyncio.create_task to prevent blocking!
    workflow.add_edge("generate_response", END)

    return workflow.compile()

companion_graph = build_graph()
