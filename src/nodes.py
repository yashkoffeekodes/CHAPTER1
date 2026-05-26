from src.schema import MainState
from src.retriever import retriever
from src.tools_api import tools_dict, tools
from src.config import llm

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langgraph.prebuilt import ToolNode

import json


# ============================================
# SEMANTIC SEARCH NODE
# ============================================
async def semantic_search(state: MainState) -> MainState:
    """
    Retrieves the most relevant tools for the user query.
    """

    try:
        print("Semantic search node triggered")

        user_query = state.get("user_query", "")

        if not user_query:
            print("No user query found")
            return {"retrieved_tools": []}

        retrieved_tools = await retriever(user_query)
        tool_names = [tool.name for tool in retrieved_tools]

        print(f"Retrieved tools: {tool_names}")

        return {"retrieved_tools": tool_names}

    except Exception as e:
        print(f"Error in semantic search node: {e}")
        return {"retrieved_tools": []}


# ============================================
# SYSTEM PROMPT
# ============================================
def build_system_prompt(user_query: str, retrieved_tools: list[str]) -> str:
    prompt = """
You are an ERP/accounting tool-calling worker.

QUERY:
__USER_QUERY__

TOOLS:
__RETRIEVED_TOOLS__

JOB:
Call only required tools from TOOLS. Do not answer directly. Python creates final JSON.

RULES:
- Use only retrieved tools.
- Multi-part query => call all required tools.
- Never invent data, fields, filters, dates, ledger IDs, or records.
- Return tool calls only.

ARGS:
term = broad search.
filters = exact filters.
fields = output columns.
limit = 10 unless user asks otherwise.
ledger_id only if numeric ledger ID is given.
from_date/to_date only if user gives dates.

TOOLS MAP:
sales/customer bills -> get_sales_list
purchase/vendor/supplier bills -> get_purchase_list
products/inventory/stock/HSN/SKU/GST -> get_product_list

FIELDS:
Always pass fields as list[str].
If a field is used in filters, include it in fields.

Invoice fields:
invoiceNo, billToName, netAmount, outstanding, status, invoiceDate,
billToState, billToCity, billToAddress, billTogstNumber,
taxableAmount, igstAmount, cgstAmount, sgstAmount.

Invoice meanings:
invoice/bill no -> invoiceNo
customer/vendor/party/supplier/buyer/grahak/vikreta -> billToName
amount/total/net/rakam/rashi -> netAmount
pending/due/outstanding/baki/thakbaki -> outstanding
status/sthiti -> status
date -> invoiceDate
state/rajya/location -> billToState
tax/GST -> taxableAmount, igstAmount, cgstAmount, sgstAmount, netAmount

Always include invoiceNo for invoice queries.

Product fields:
name, hsn, closingQty, closingRate, igst, cgst, sgst, sku, uom.

Product meanings:
product/item/name -> name
HSN -> hsn
stock/quantity/jaththo/satha -> closingQty
rate/price -> closingRate
GST/tax -> igst, cgst, sgst

Always include name for product queries unless user asks only numbers.

FILTERS:
filters must be JSON object.
Use term + filters when possible.
Never use fields for filtering.
Never use filters for output columns.

Filter patterns:
sales invoice X -> term=X, filters={"invoiceNo":X}
purchase invoice X -> term=X, filters={"invoiceNo":X}
HSN X -> term=X, filters={"hsn":X}
state X -> term=X, filters={"billToState":X}
status X -> filters={"status":X}
amount > N -> filters={"netAmount":{"gt":N}}
amount < N -> filters={"netAmount":{"lt":N}}
outstanding > N -> filters={"outstanding":{"gt":N}}
outstanding < N -> filters={"outstanding":{"lt":N}}
closing quantity > N -> filters={"closingQty":{"gt":N}}
closing quantity < N -> filters={"closingQty":{"lt":N}}
A or B -> filters={field:{"in":[A,B]}}

Filter ops:
eq, contains, in, gt, gte, lt, lte.

MULTILINGUAL ALIASES:
show = dikhao/batao/batavo/dakhva
and = aur/ane/ani
of = ka/ke/ki/no/nu/na/cha/chi/che
with = wale/vala/sathe/sobat
where = jisme/jema/madhle
greater than = zyada/vadhu/jast/adhik
less than = kam/ochhi/ochhu/ochha/kami

Phrase filters:
0 se zyada, 0 karta vadhu, 0 peksha jast -> {"gt":0}
0 se kam, 0 karta ochhi, 0 karta ochhu, 0 karta ochha, 0 peksha kami -> {"lt":0}

COMMON FIELD SETS:
customer/vendor + amount -> ["invoiceNo","billToName","netAmount"]
status -> ["invoiceNo","status"]
pending/outstanding -> ["invoiceNo","outstanding"]
invoice GST/tax -> ["invoiceNo","taxableAmount","igstAmount","cgstAmount","sgstAmount","netAmount"]
product stock -> ["name","hsn","closingQty"]
product GST/tax -> ["name","hsn","igst","cgst","sgst"]
product stock + GST -> ["name","hsn","closingQty","igst","cgst","sgst"]

AMBIGUITY:
If invoice number returns multiple records, return all matches. Never pick first unless user gives extra filters.

FULL RECORD:
Use fields=[] only if user asks full details/raw JSON/all fields/full record.

FINAL:
Only call tools. Never generate final answer text.
"""
    return (
        prompt
        .replace("__USER_QUERY__", user_query)
        .replace("__RETRIEVED_TOOLS__", str(retrieved_tools))
    )
# ============================================
# CHAT MODEL NODE
# ============================================
async def chat_model_node(state: MainState):
    """
    LLM node used only for deciding tool calls.
    Final response is built later by deterministic_final_node.
    """

    loop_count = state.get("loop_count", 0)
    user_query = state.get("user_query", "")
    messages = state.get("messages", [])
    retrieved_tools = state.get("retrieved_tools", [])

    try:
        print("Chat model node called...")

        available_tools = [
            tools_dict[name]
            for name in retrieved_tools
            if name in tools_dict
        ]

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

        if not messages:
            messages = [HumanMessage(content=user_query)]

        system_prompt = SystemMessage(
            content=build_system_prompt(
                user_query=user_query,
                retrieved_tools=retrieved_tools
            )
        )

        llm_input = [system_prompt] + messages

        response = await llm_with_tools.ainvoke(llm_input)

        return {
            "messages": messages + [response],
            "loop_count": loop_count + 1,
        }

    except Exception as e:
        print(f"Error in chat model node: {e}")

        return {
            "messages": messages + [AIMessage(content=f"Error: {str(e)}")],
            "loop_count": loop_count + 1,
        }


# ============================================
# ROUTING NODE
# ============================================
async def routing_node(state: MainState):
    """
    Routes to tools if the LLM requested tool calls.
    Otherwise ends the graph.
    """

    try:
        print("Routing node activated............")

        messages = state.get("messages", [])

        if not messages:
            return "__end__"

        last_message = messages[-1]

        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"

        loop_count = state.get("loop_count", 0)

        if loop_count > 5:
            return "__end__"

        print("No tool call is detected, ending the graph...")
        return "__end__"

    except Exception as e:
        print(f"Error in routing node: {e}")
        return "__end__"


# ============================================
# DETERMINISTIC FINAL NODE HELPERS
# ============================================
def parse_tool_output(content):
    """
    Converts ToolMessage content into Python dict.
    Tool output usually comes as JSON string.
    """

    try:
        if isinstance(content, dict):
            return content

        if isinstance(content, list):
            return {
                "success": True,
                "data": content,
                "count": len(content),
                "error": None,
            }

        return json.loads(content)

    except Exception as e:
        return {
            "success": False,
            "data": [],
            "count": 0,
            "error": f"Could not parse tool output: {str(e)}",
        }


def get_tool_name(tool_message, messages):
    """
    Gets tool name from ToolMessage.
    Fallback: match ToolMessage.tool_call_id with AIMessage.tool_calls.
    """

    tool_name = getattr(tool_message, "name", None)

    if tool_name:
        return tool_name

    tool_call_id = getattr(tool_message, "tool_call_id", None)

    for msg in messages:
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            for call in msg.tool_calls:
                if call.get("id") == tool_call_id:
                    return call.get("name")

    return "unknown_tool"


def make_summary(data: dict, errors: list) -> str:
    """
    Creates a simple deterministic summary.
    """

    parts = []

    for tool_name, records in data.items():
        count = len(records) if isinstance(records, list) else 0

        if count == 0:
            parts.append(f"{tool_name}: no records found")
        elif count == 1:
            parts.append(f"{tool_name}: found 1 record")
        else:
            parts.append(f"{tool_name}: found {count} records")

    if errors:
        parts.append(f"{len(errors)} error(s)")

    return "; ".join(parts)


# ============================================
# DETERMINISTIC FINAL NODE
# ============================================
async def deterministic_final_node(state: MainState):
    """
    Builds final JSON using Python, not LLM.
    This removes the second LLM call.
    """

    user_query = state.get("user_query", "")
    messages = state.get("messages", [])

    data = {}
    tools_used = []
    errors = []

    tool_messages = [
        msg for msg in messages
        if isinstance(msg, ToolMessage)
    ]

    for tool_msg in tool_messages:
        tool_name = get_tool_name(tool_msg, messages)

        if tool_name not in tools_used:
            tools_used.append(tool_name)

        parsed = parse_tool_output(tool_msg.content)

        if not parsed.get("success"):
            data.setdefault(tool_name, [])

            errors.append({
                "tool": tool_name,
                "error": parsed.get("error", "Unknown tool error"),
            })

            continue

        records = parsed.get("data", [])

        if records is None:
            records = []

        if not isinstance(records, list):
            records = [records]

        data.setdefault(tool_name, [])
        data[tool_name].extend(records)

    has_any_data = any(
    isinstance(records, list) and len(records) > 0
    for records in data.values()
    )

    has_empty_requested_sections = any(
        isinstance(records, list) and len(records) == 0
        for records in data.values()
    )

    if errors and has_any_data:
        status = "partial_success"
        success = True

    elif errors and not has_any_data:
        status = "error"
        success = False

    elif has_any_data and has_empty_requested_sections:
        status = "partial_success"
        success = True

    elif has_any_data:
        status = "success"
        success = True

    else:
        status = "no_matching_records"
        success = False

    final_response = {
        "success": success,
        "status": status,
        "query": user_query,
        "tools_used": tools_used,
        "data": data,
        "summary": make_summary(data, errors),
        "errors": errors,
    }

    return {
        "final_response": json.dumps(final_response, ensure_ascii=False),
        "tools_utilized": tools_used,
    }


# ============================================
# TOOL NODE
# ============================================
tools_node = ToolNode(tools)











# You are an ERP/accounting tool-calling worker inside a LangGraph app.

# ORIGINAL USER QUERY:
# {user_query}

# RETRIEVED TOOLS:
# {retrieved_tools}

# Your only job:
# - Decide which retrieved tools must be called.
# - Call every required retrieved tool.
# - Do not produce the final answer yourself.

# Tool rules:
# - Use only tools listed in RETRIEVED TOOLS.
# - If RETRIEVED TOOLS contains multiple tools and the user query has multiple parts, call all required tools.
# - Use term for invoice number, party name, customer name, supplier name, product name, SKU, HSN, reference number, or search keyword.
# - Use ledger_id only if the user provides a ledger ID.
# - Use from_date and to_date only if the user provides a date range.
# - Use fields only if the user asks for specific columns.
# - Do not invent tool arguments.
# - Do not answer using general knowledge.
# TOOL ARGUMENT RULES:

# You must call tools with structured arguments.

# When the user asks for specific fields, pass those fields in the `fields` argument.

# Example:
# User: Find sales invoice A/0326/C0077 and return only invoiceNo, invoiceDate, netAmount
# Tool call:
# get_sales_list(
#   filters={"invoiceNo": "A/0326/C0077"},
#   fields=["invoiceNo", "invoiceDate", "netAmount"],
#   limit=10
# )

# Do not request full records when the user asks for selected fields.

# Do not filter records yourself.
# Filtering must happen through tool arguments.

# Use filters for exact conditions:
# - invoice number → filters={"invoiceNo": "..."}
# - state → filters={"billToState": "..."}
# - customer/vendor name → filters={"billToName": "..."}
# - HSN → filters={"hsn": "..."}
# - closing quantity → filters={"closingQty": ...}

# Use fields for output columns requested by the user.

# If the user does not ask for specific fields, do not pass fields. The deterministic final node will use default fields.

# Never invent field names. Use only fields that appear in the ERP records.
# Important:
# - The retriever has already selected the most relevant tools.
# - Your role is only to call the correct retrieved tools with correct arguments.
# - The final response will be created by Python after tools finish.
# """
