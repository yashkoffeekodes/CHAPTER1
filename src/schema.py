from typing import Annotated, List, Literal, TypedDict, Dict, Any
from operator import add
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class InputState(TypedDict):
    user_query : str


class MainState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_query: str
    retrieved_tools: List[str]
    loop_count: int
    final_response: str
    tools_utilized: List[str]       
    step_timings: Annotated[List[Dict[str, Any]], add]
class OutputState(TypedDict):
    final_response: str
    tools_utilized: List[str]   
    step_timings: List[Dict[str, Any]]
class SupervisorState(BaseModel):
    reasoning:str = Field(
        description="Explain your thought process before making a routing decision."
    )
    next_node: Literal["worker_node","tools_node","FINISH"] = Field(
        description="The exact next node the graph must route to."
    )