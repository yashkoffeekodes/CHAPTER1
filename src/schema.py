from typing import Annotated, List, Optional
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class InputState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]


class MainState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    selected_tool_names: List[str]
    detected_intents: List[str]
    detected_item: Optional[str]


class OutputState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]