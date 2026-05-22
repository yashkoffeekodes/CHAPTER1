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
    data: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    response: DynamicERPResponse

def extract_json_from_llm_response(text: str) -> dict:
    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    return json.loads(cleaned)


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
                    if not getattr(last_msg, "tool_calls", None):
                        final_ans = last_msg.content
        
        final_response = extract_json_from_llm_response(final_ans)
        return ChatResponse(response=final_response or "No response generated.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "fast_main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )