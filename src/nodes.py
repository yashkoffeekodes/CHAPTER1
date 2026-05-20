from src.retriever import retriever
from src.schema import MainState,InputState,OutputState,SupervisorState
from src.config import llm
from src.tool import tools_dict,tools
import asyncio
from langchain_core.messages import SystemMessage,HumanMessage,AIMessage,ToolMessage
from langgraph.prebuilt import ToolNode


# 1. our semantic search node

async def semantic_search_node(state:MainState):
    try:
        query = state['user_query']
        print(f"Semantic search node activated and is analysing the user's query : {query}")

        retrieved_tools = await retriever(query, k=7)
        retrieved_tools_names = [tool.name for tool in retrieved_tools]
        print(f"Retrieved tools : {retrieved_tools_names}")
        return {
            "retrieved_tools": retrieved_tools_names
        }
    except Exception as e:
        print(f"Error in semantic search node: {e}")


#2. our worker node the chatbot node

async def chatbot_node(state:MainState):
    """Binds the active tools to the LLM and generates a response or tool calls."""
    try:
        print("\n Chatbot Node is activated..........")
        messages = state["messages"]
        loop_count = state.get("loop_count",0)
        retrieved_tools = state.get("retrieved_tools", [])
        tools_list = [tools_dict[name] for name in retrieved_tools if name in tools_dict]
        if tools_list:
            print("Binding the tools with LLM................")
            llm_with_tools = llm.bind_tools(tools_list)
            print("LLM with tools bound successfully")
        sys_prompt = SystemMessage(
            content=(
               "You are an advanced ERP & Accounting Assistant.\n"
                "Use the provided tools to find the data required to answer the user's query.\n\n"
                f"THE USER'S EXACT QUERY IS: '{state['user_query']}'\n\n"
                "CRITICAL INSTRUCTIONS:\n"
                "1. If the user asks for multiple pieces of data, call multiple tools in parallel.\n"
                "2. NEVER hallucinate or change tool arguments.\n"
                "3. ONLY answer exactly what the user explicitly asked for based on the tool data.\n"
                "4. Be extremely concise and direct. Do not make up dates or names."
            )
        )
        response = await llm_with_tools.ainvoke([sys_prompt] + messages)
        print("Response has been generated sucessfully")
        return {
            "messages": [response],
            "loop_count" : loop_count + 1
        }
    except Exception as e:
        print(f"Error in our worker node is {e}")
        return {
            "messages" : [AIMessage(content=f"An internal error occured : {str(e)}")]
        }

tool_node = ToolNode(tools)

async def supervisor_node(state:MainState):
    """
      This node will be used for routing logic and guide the llm in choosing whether 
      the chatbot should continue with the task,try again or end it.
    """
    try:
            
        print("\nThe supervisor  node has been activated anb is evaluating..............")
        messages = state["messages"]
        last_message = messages[-1]
        if hasattr(last_message,"tool_calls") and last_message.tool_calls:
            print("Tool call action is detected routing to TOOLS NODE>>>>>>>>>>>>.")
            return "tools_node"
        if state.get("loop_count", 0) > 10:
            print("Maximum loop count reached, ending the conversation.")
            return "__end__"
        system_prompt = SystemMessage(
            content=(
                "You are a Quality Assurance Supervisor for an ERP AI.\n"
                "Review the conversation history. Did the worker fully and accurately "
                "answer the user's original query?\n"
                "- If YES, route to 'FINISH'.\n"
                "- If NO (the worker hallucinated, gave an incomplete answer, or needs "
                "to try a different approach), route back to 'worker_node'."
            )
        )
        supervisor_llm = llm.with_structured_output(SupervisorState)
        print("Supervisor LLM initiated.........")
        response = await supervisor_llm.ainvoke([system_prompt] + messages)
        print("Supervisor response received.........")
        if response.next_node == "FINISH":
            return "__end__"

        return response.next_node
    except Exception as e:
        print(f"Exception of routing  node  is {e}")
        print("↳ Routing to '__end__' to prevent graph crash.")
        return "__end__"
