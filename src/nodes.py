from typing import Dict, Any,Literal
from src.schema import MainState,SupervisorState
from src.retriever import retriever
from src.tools import tools_dict,tools
from src.config import llm
from langchain_core.messages import HumanMessage,SystemMessage,AIMessage,ToolMessage
from langgraph.prebuilt import ToolNode



# ============================================
# SEMANTIC SEARCH NODE
# ============================================
async def semantic_search(state: MainState) -> MainState:
    """
    Node responsible for interpreting the user query and fetching the 
    most relevant tools using the vector store.
    """
    try:
        print("Semantic search node triggered")
        user_query = state.get("user_query", "")
        
        if not user_query:
            print("No user query found")
            return {"retrieved_tools": []}
        retrived_tools = await retriever(user_query)
        tool_names = [tool.name for tool in retrived_tools]
        print(f"Retrieved tools: {tool_names}")
        return {"retrieved_tools": tool_names}
    except Exception as e:
        print(f"Error in semantic search node: {e}")
        return {"retrieved_tools": []}



# ============================================
# CHAT-MODEL-NODE
# ============================================
def build_system_prompt(user_query: str, retrieved_tools: list[str]) -> str:
    return f"""
You are an ERP/accounting AI worker inside a LangGraph app.

ORIGINAL USER QUERY:
{user_query}

RETRIEVED TOOLS:
{retrieved_tools}

Your job:
1. If tool outputs are not available, call all relevant retrieved tools.
2. If tool outputs are available, answer using ONLY tool data.
3. Filter records according to the original user query.
4. Return compact JSON only.

Tool rules:
- Use only retrieved tools.
- If multiple tools are needed, call all of them.
- Do not answer before tool outputs are available.
- Current tools usually return raw ERP lists, so call them with empty args unless the tool schema clearly supports args.
Out-of-scope rules:
- You are only allowed to answer ERP/accounting/inventory questions using retrieved tool data.
- If the user asks something unrelated to ERP/accounting/inventory, do not call tools.
- If no retrieved tool is relevant to the user query, return an out_of_scope JSON response.
- If the user asks for ERP/accounting data but the required tool was not retrieved, return partial_success or error; do not guess.
- If tool output does not contain the requested information, return [] or null. Never use general knowledge.
No-hallucination rules:
- Never invent records, names, invoices, products, states, dates, amounts, rates, or quantities.
- If no matching records exist for a called tool, return [] for that tool.
- Every returned value must come from tool output.

Filtering rules:
- Purchase/sales state: match billToState or shipToState exactly, case-insensitive.
- Invoice number: match invoiceNo exactly, case-insensitive.
- Party/customer/supplier: match billToName or shipToName partially, case-insensitive.
- Negative stock: closingQty < 0.
- Positive stock: closingQty > 0.
- Zero stock: closingQty == 0.
- Outstanding: outstanding > 0.

Output rules:
- Output one JSON object only.
- No markdown.
- No code fences.
- Keep fields compact.
- Use actual called tool names as keys inside data.
- tools_used must include every called tool.
- query must exactly equal the original user query.

Status rules:
- success: tools ran and at least one section has matches.
- no_matching_records: tools ran but all sections are empty.
- partial_success: at least one required tool failed or was unavailable.
- error: runtime/system/tool-output error.

JSON shape:
{{
  "success": true,
  "status": "success",
  "query": "{user_query}",
  "tools_used": [],
  "data": {{}},
  "summary": "",
  "errors": []
}}
"""

async def chat_model_node(state: MainState):
    loop_count = state.get("loop_count", 0)
    user_query = state.get("user_query", "")
    
    # Get existing messages, default to empty list
    messages = state.get("messages", [])
    retrieved_tools = state.get("retrieved_tools", [])
    
    try:
        print("Chat model node called...")

        # Setup tools
        available_tools = [tools_dict[name] for name in retrieved_tools if name in tools_dict]
        has_tool_outputs = any(
            isinstance(msg, ToolMessage)
            for msg in messages
        )
        if available_tools and not has_tool_outputs:
            llm_with_tools = llm.bind_tools(available_tools)
            print("Tools bound to LLM")
        else:
            llm_with_tools = llm
            print("No tools bound to LLM")
            
        # If it's the very first turn, start with a HumanMessage
        if not messages:
            messages = [HumanMessage(content=user_query)]
            messages_to_return = messages.copy()
        else:
            messages_to_return = []
        # Prepare system prompt
        system_prompt = SystemMessage(
            content=build_system_prompt(user_query=user_query, retrieved_tools=retrieved_tools)
        )

        # Send full history to LLM
        llm_input = [system_prompt] + messages
        response = await llm_with_tools.ainvoke(llm_input)

        # Return updated state: Append the new response to the existing list
        return {
            "messages": messages + [response],
            "loop_count": loop_count + 1
        }

    except Exception as e:
        print(f"Error in chat model node: {e}")
        # Keep existing messages to prevent data loss
        return {
            "messages": messages + [AIMessage(content=f"Error: {str(e)}")],
            "loop_count": loop_count + 1
        }
    
tools_node = ToolNode(tools)