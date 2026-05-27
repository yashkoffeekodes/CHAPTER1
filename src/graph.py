from langgraph.graph import StateGraph, END, START
from src.schema import MainState, InputState, OutputState
from src.nodes import (
    semantic_search,
    chat_model_node,
    tools_node,
    routing_node,
    deterministic_final_node,
    router_node,
    canonicalizer_node
)
import time
import inspect


def timed_node(node_name: str, node_func):
    async def wrapper(state):
        start = time.perf_counter()

        try:
            if inspect.iscoroutinefunction(node_func):
                result = await node_func(state)
            elif hasattr(node_func, "ainvoke"):
                result = await node_func.ainvoke(state)
            else:
                result = node_func(state)

            duration = time.perf_counter() - start
            print(f"[TIMING] {node_name} took {duration:.3f}s")

            if result is None:
                result = {}

            if isinstance(result, dict):
                result["step_timings"] = [
                    {
                        "node": node_name,
                        "duration_sec": round(duration, 3),
                    }
                ]

            return result

        except Exception as e:
            duration = time.perf_counter() - start
            print(f"[TIMING] {node_name} failed after {duration:.3f}s")

            return {
                "step_timings": [
                    {
                        "node": node_name,
                        "duration_sec": round(duration, 3),
                        "error": str(e),
                    }
                ]
            }

    return wrapper


# ADD THIS FUNCTION BEFORE graph_builder()
def route_after_semantic(state: MainState):
    if state.get("skip_router", False):
        print("Skipping router because semantic_search already selected tools")
        return "chat_model"

    return "router"


def graph_builder():
    try:
        print("Building graph...")

        builder = StateGraph(
            MainState,
            input_schema=InputState,
            output_schema=OutputState,
        )
        builder.add_node("canonicalizer", timed_node("canonicalizer", canonicalizer_node))
        builder.add_node("semantic_search", timed_node("semantic_search", semantic_search))
        builder.add_node("chat_model", timed_node("chat_model", chat_model_node))
        builder.add_node("tools", timed_node("tools", tools_node))
        builder.add_node("router", timed_node("router", router_node))
        builder.add_node(
            "deterministic_final",
            timed_node("deterministic_final", deterministic_final_node),
        )

        builder.add_edge(START, "canonicalizer")
        builder.add_edge("canonicalizer", "semantic_search")
        builder.add_conditional_edges(
            "semantic_search",
            route_after_semantic,
            {
                "chat_model": "chat_model",
                "router": "router",
            },
        )

        builder.add_edge("router", "chat_model")

        builder.add_conditional_edges(
            "chat_model",
            routing_node,
            {
                "tools": "tools",
                "__end__": END,
            },
        )

        builder.add_edge("tools", "deterministic_final")
        builder.add_edge("deterministic_final", END)

        graph = builder.compile()

    except Exception as e:
        print(f"Error building graph: {e}")
        raise e

    return graph