from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from src.graph import graph_builder
import json
import re
import time
from typing import Any, Dict, List
import uvicorn

app = FastAPI(
    title="ERP Assistant API",
    version="1.0.0"
)

# Build graph once when server starts
graph = graph_builder()


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    response: Dict[str, Any]
    timings: List[Dict[str, Any]]
    total_time_sec: float


def parse_llm_json(text: str):
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


async def run_graph_query(user_query: str) -> Dict[str, Any]:
    start_time = time.perf_counter()

    initial_state = {
        "user_query": user_query,
        "messages": [],
        "retrieved_tools": [],
        "loop_count": 0,
        "final_response": "",
        "tools_utilized": [],
        "step_timings": []
    }

    final_response = None
    timings = []

    async for chunks in graph.astream(initial_state, stream_mode="updates"):
        for node_name, state_update in chunks.items():
            print(f"Finished running: {node_name}")

            if "step_timings" in state_update:
                timings.extend(state_update["step_timings"])

                for timing in state_update["step_timings"]:
                    print(
                        f"[STEP TIME] {timing['node']} = {timing['duration_sec']}s"
                    )

            if node_name == "chat_model":
                messages = state_update.get("messages", [])

                if not messages:
                    continue

                last_message = messages[-1]

                # First chat_model call usually returns tool calls
                if getattr(last_message, "tool_calls", None):
                    print("Tool calls requested:")

                    for tool_call in last_message.tool_calls:
                        print(
                            f"- {tool_call['name']} args={tool_call.get('args', {})}"
                        )

                    continue

                # Final chat_model call returns JSON content
                if getattr(last_message, "content", None):
                    parsed = parse_llm_json(last_message.content)

                    if parsed is not None:
                        final_response = parsed
                    else:
                        final_response = {
                            "success": False,
                            "status": "invalid_json_response",
                            "query": user_query,
                            "tools_used": [],
                            "data": {},
                            "summary": last_message.content,
                            "errors": ["LLM returned a non-JSON response."]
                        }

    total_time = round(time.perf_counter() - start_time, 3)

    if final_response is None:
        final_response = {
            "success": False,
            "status": "no_final_response",
            "query": user_query,
            "tools_used": [],
            "data": {},
            "summary": "The graph completed without producing a final response.",
            "errors": ["No final chat_model response found."]
        }

    return {
        "response": final_response,
        "timings": timings,
        "total_time_sec": total_time
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
            detail={
                "success": False,
                "status": "server_error",
                "query": request.query,
                "data": {},
                "summary": "Server error while processing the query.",
                "errors": [str(e)]
            }
        )

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
