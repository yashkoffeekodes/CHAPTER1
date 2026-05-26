from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from src.graph import graph_builder

import json
import re
import time
import asyncio
from typing import Any, Dict, List

import uvicorn


app = FastAPI(
    title="CHAPTER-1-ASSIST",
    version="1.0.0"
)

GRAPH_TIMEOUT_SECONDS = 300

# Build graph once when server starts
graph = graph_builder()


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    response: Dict[str, Any]
    timings: List[Dict[str, Any]]
    total_time_sec: float


def parse_json_safely(text: str):
    """
    Safely parse JSON from a string.
    Works for raw JSON and accidental markdown-wrapped JSON.
    """

    if not text:
        return None

    cleaned = text.strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)

    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def make_error_response(
    user_query: str,
    status: str,
    summary: str,
    errors: List[str],
    tools_used: List[str] | None = None,
    data: Dict[str, Any] | None = None,
):
    return {
        "success": False,
        "status": status,
        "query": user_query,
        "tools_used": tools_used or [],
        "data": data or {},
        "summary": summary,
        "errors": errors,
    }


async def run_graph_query(user_query: str) -> Dict[str, Any]:
    start_time = time.perf_counter()

    initial_state = {
        "user_query": user_query,
        "messages": [],
        "retrieved_tools": [],
        "loop_count": 0,
        "final_response": "",
        "tools_utilized": [],
        "step_timings": [],
    }

    final_response = None
    timings = []
    tools_requested = []

    try:
        async with asyncio.timeout(GRAPH_TIMEOUT_SECONDS):
            async for chunks in graph.astream(initial_state, stream_mode="updates"):
                for node_name, state_update in chunks.items():
                    print(f"Finished running: {node_name}")

                    # Collect timings from timed_node wrapper
                    if "step_timings" in state_update:
                        timings.extend(state_update["step_timings"])

                        for timing in state_update["step_timings"]:
                            print(
                                f"[STEP TIME] {timing['node']} = {timing['duration_sec']}s"
                            )

                    # First LLM call: tool planning/tool calling only
                    if node_name == "chat_model":
                        messages = state_update.get("messages", [])

                        if not messages:
                            continue

                        last_message = messages[-1]

                        if getattr(last_message, "tool_calls", None):
                            print("Tool calls requested:")

                            for tool_call in last_message.tool_calls:
                                tool_name = tool_call.get("name")
                                tool_args = tool_call.get("args", {})

                                if tool_name and tool_name not in tools_requested:
                                    tools_requested.append(tool_name)

                                print(f"- {tool_name} args={tool_args}")

                            continue

                        # Fallback case:
                        # If graph ends after chat_model without tools, capture its response.
                        # This can happen for out-of-scope or error responses.
                        content = getattr(last_message, "content", None)

                        if content:
                            parsed = parse_json_safely(content)

                            if parsed is not None:
                                final_response = parsed
                            else:
                                final_response = make_error_response(
                                    user_query=user_query,
                                    status="no_tool_call",
                                    summary=content,
                                    errors=[
                                        "chat_model ended without tool calls and did not return valid JSON."
                                    ],
                                    tools_used=tools_requested,
                                )

                    # Final Python merger:
                    # This replaces the second LLM call.
                    if node_name == "deterministic_final":
                        final_response_raw = state_update.get("final_response")
                        tools_utilized = state_update.get("tools_utilized", [])

                        if isinstance(final_response_raw, dict):
                            final_response = final_response_raw

                        elif isinstance(final_response_raw, str):
                            parsed = parse_json_safely(final_response_raw)

                            if parsed is not None:
                                final_response = parsed
                            else:
                                final_response = make_error_response(
                                    user_query=user_query,
                                    status="invalid_final_json",
                                    summary=final_response_raw,
                                    errors=[
                                        "deterministic_final returned invalid JSON."
                                    ],
                                    tools_used=tools_utilized,
                                )

                        else:
                            final_response = make_error_response(
                                user_query=user_query,
                                status="missing_final_response",
                                summary="deterministic_final did not return final_response.",
                                errors=[
                                    "No final_response found in deterministic_final node output."
                                ],
                                tools_used=tools_utilized,
                            )

    except TimeoutError:
        total_time = round(time.perf_counter() - start_time, 3)

        return {
            "response": make_error_response(
                user_query=user_query,
                status="graph_timeout",
                summary="The graph exceeded the timeout limit.",
                errors=[
                    f"Graph execution timed out after {GRAPH_TIMEOUT_SECONDS} seconds."
                ],
                tools_used=tools_requested,
            ),
            "timings": timings,
            "total_time_sec": total_time,
        }

    except Exception as e:
        total_time = round(time.perf_counter() - start_time, 3)

        return {
            "response": make_error_response(
                user_query=user_query,
                status="graph_error",
                summary="Error while running the graph.",
                errors=[str(e)],
                tools_used=tools_requested,
            ),
            "timings": timings,
            "total_time_sec": total_time,
        }

    total_time = round(time.perf_counter() - start_time, 3)

    if final_response is None:
        final_response = make_error_response(
            user_query=user_query,
            status="no_final_response",
            summary="The graph completed without producing a final response.",
            errors=[
                "No deterministic_final response found. Check graph.py flow."
            ],
            tools_used=tools_requested,
        )

    return {
        "response": final_response,
        "timings": timings,
        "total_time_sec": total_time,
    }


@app.get("/")
async def root():
    return {
        "message": "ERP Assistant API is running"
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        return await run_graph_query(request.query)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=make_error_response(
                user_query=request.query,
                status="server_error",
                summary="Server error while processing the query.",
                errors=[str(e)],
            ),
        )


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)


# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel, Field
# from src.graph import graph_builder
# import json
# import re
# import time
# import asyncio
# from typing import Any, Dict, List
# import uvicorn


# app = FastAPI(
#     title="CHAPTER-1-ASSIST",
#     version="1.0.0"
# )

# GRAPH_TIMEOUT_SECONDS = 300  # 5 minutes timeout

# # Build graph once when server starts
# graph = graph_builder()


# class ChatRequest(BaseModel):
#     query: str = Field(..., min_length=1)


# class ChatResponse(BaseModel):
#     response: Dict[str, Any]
#     timings: List[Dict[str, Any]]
#     total_time_sec: float


# def parse_llm_json(text: str):
#     if not text:
#         return None

#     cleaned = text.strip()
#     cleaned = cleaned.replace("```json", "").replace("```", "").strip()

#     try:
#         return json.loads(cleaned)
#     except json.JSONDecodeError:
#         pass

#     match = re.search(r"\{.*\}", cleaned, re.DOTALL)

#     if match:
#         try:
#             return json.loads(match.group(0))
#         except json.JSONDecodeError:
#             pass

#     return None


# async def run_graph_query(user_query: str) -> Dict[str, Any]:
#     start_time = time.perf_counter()

#     initial_state = {
#         "user_query": user_query,
#         "messages": [],
#         "retrieved_tools": [],
#         "loop_count": 0,
#         "final_response": "",
#         "tools_utilized": [],
#         "step_timings": []
#     }

#     final_response = None
#     timings = []

#     try:
#         async with asyncio.timeout(GRAPH_TIMEOUT_SECONDS):
#             async for chunks in graph.astream(initial_state, stream_mode="updates"):
#                 for node_name, state_update in chunks.items():
#                     print(f"Finished running: {node_name}")

#                     if "step_timings" in state_update:
#                         timings.extend(state_update["step_timings"])

#                         for timing in state_update["step_timings"]:
#                             print(
#                                 f"[STEP TIME] {timing['node']} = {timing['duration_sec']}s"
#                             )

#                     if node_name == "chat_model":
#                         messages = state_update.get("messages", [])

#                         if not messages:
#                             continue

#                         last_message = messages[-1]

#                         # First chat_model call usually returns tool calls
#                         if getattr(last_message, "tool_calls", None):
#                             print("Tool calls requested:")

#                             for tool_call in last_message.tool_calls:
#                                 print(
#                                     f"- {tool_call['name']} args={tool_call.get('args', {})}"
#                                 )

#                             continue

#                         # Final chat_model call returns JSON content
#                         if getattr(last_message, "content", None):
#                             parsed = parse_llm_json(last_message.content)

#                             if parsed is not None:
#                                 final_response = parsed
#                             else:
#                                 final_response = {
#                                     "success": False,
#                                     "status": "invalid_json_response",
#                                     "query": user_query,
#                                     "tools_used": [],
#                                     "data": {},
#                                     "summary": last_message.content,
#                                     "errors": ["LLM returned a non-JSON response."]
#                                 }

#     except TimeoutError:
#         total_time = round(time.perf_counter() - start_time, 3)

#         return {
#             "response": {
#                 "success": False,
#                 "status": "graph_timeout",
#                 "query": user_query,
#                 "tools_used": [],
#                 "data": {},
#                 "summary": "The graph exceeded the 5-minute timeout limit.",
#                 "errors": [
#                     f"Graph execution timed out after {GRAPH_TIMEOUT_SECONDS} seconds."
#                 ]
#             },
#             "timings": timings,
#             "total_time_sec": total_time
#         }

#     except Exception as e:
#         total_time = round(time.perf_counter() - start_time, 3)

#         return {
#             "response": {
#                 "success": False,
#                 "status": "graph_error",
#                 "query": user_query,
#                 "tools_used": [],
#                 "data": {},
#                 "summary": "Error while running the graph.",
#                 "errors": [str(e)]
#             },
#             "timings": timings,
#             "total_time_sec": total_time
#         }

#     total_time = round(time.perf_counter() - start_time, 3)

#     if final_response is None:
#         final_response = {
#             "success": False,
#             "status": "no_final_response",
#             "query": user_query,
#             "tools_used": [],
#             "data": {},
#             "summary": "The graph completed without producing a final response.",
#             "errors": ["No final chat_model response found."]
#         }

#     return {
#         "response": final_response,
#         "timings": timings,
#         "total_time_sec": total_time
#     }


# @app.get("/")
# async def root():
#     return {
#         "message": "ERP Assistant API is running"
#     }


# @app.post("/chat", response_model=ChatResponse)
# async def chat(request: ChatRequest):
#     try:
#         return await run_graph_query(request.query)

#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail={
#                 "success": False,
#                 "status": "server_error",
#                 "query": request.query,
#                 "data": {},
#                 "summary": "Server error while processing the query.",
#                 "errors": [str(e)]
#             }
#         )


# if __name__ == "__main__":
#     uvicorn.run(app, host="127.0.0.1", port=8000)