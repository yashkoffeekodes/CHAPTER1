from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,Field
from langchain_core.messages import HumanMessage
from uuid import uuid4
from src.graphs import graph_builder
from typing import Any
import json 
import re

app = FastAPI(title="CHAPTER1 AI ASSISTANT")

class DynamicERPResponse(BaseModel):
    success: bool = True
    query: str
    status: str = "success"
    data: dict[str, Any] = Field(default_factory=dict)

    
class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    response: DynamicERPResponse

def extract_json_from_llm_response(text: str, query: str) -> dict:
    cleaned = (text or "").strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "success": False,
            "query": query,
            "status": "invalid_llm_json",
            "data": {},
            "raw_response": cleaned
        }
def response_shape(response: dict[str, Any], query: str) -> dict[str, Any]:
    """
    Keep only the top-level API structure fixed.

    We DO NOT modify anything inside data because ERP output is dynamic.
    """

    # If model accidentally returns {"response": {...}}, unwrap it
    if "response" in response and isinstance(response["response"], dict):
        response = response["response"]

    data = response.get("data", {})

    if not isinstance(data, dict):
        data = {}

    return {
        "success": response.get("success", True),
        "query": response.get("query", query),
        "status": response.get("status", "success"),
        "data": data
    }


@app.get("/")
async def root():
    return {"status": "API is running"}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        query = request.query
        initial_state = {
            "user_query": query,
            "messages": [HumanMessage(content=query)],
            "retrieved_tools": []
        }
        config = {
            "configurable": {
                "thread_id": "default"
            }
        }
        
        final_ans = None

        async for chunk in graph_builder().astream(initial_state, config=config, stream_mode="updates"):
            for node_name, node_output in chunk.items():
                
                if node_name == "worker_node" and "messages" in node_output:
                    last_msg = node_output["messages"][-1]

                    # Still has tool calls — not the final answer yet
                    if getattr(last_msg, "tool_calls", None):
                        print("Tool calls detected, waiting...")
                        continue

                    # Final answer pass
                    if hasattr(last_msg, "content") and last_msg.content:
                        final_ans = last_msg.content
                        print(f"Final answer captured: {final_ans[:100]}")
                    else:
                        final_ans = '{"success":false,"query":"' + query + '","status":"invalid_or_unclear_query","data":{}}'

        # Guard — stream ended but no final answer was captured
        if not final_ans:
            print("WARNING: final_ans is None after stream ended")
            final_ans = '{"success":false,"query":"' + query + '","status":"partial_success","data":{}}'

        # Safe JSON extraction
        final_response = extract_json_from_llm_response(final_ans, query)        
        if not final_response:
            print("WARNING: extract_json_from_llm_response returned None")
            return ChatResponse(response={
                "success": False,
                "query": query,
                "status": "invalid_or_unclear_query",
                "data": {}
            })

        structured_response = response_shape(final_response, query)
        
        return ChatResponse(response=structured_response or {
            "success": False,
            "query": query,
            "status": "invalid_or_unclear_query",
            "data": {}
        })

    except Exception as e:
        print(f"ERROR in /chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "fast_main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )