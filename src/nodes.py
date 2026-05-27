from src.schema import MainState
from src.retriever import retriever
from src.tools_api import tools_dict, tools
from src.tool_doc import TOOL_INTENT_REGISTRY
from src.config import llm,router_llm,normalizer_llm
import time
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langgraph.prebuilt import ToolNode
import json
import re
from langsmith import traceable
CANONICALIZER_PROMPT = """
You convert ERP/accounting queries written in English, Hindi, Hinglish, Gujarati, or mixed language into simple canonical English.

Return ONLY raw JSON. No markdown. No explanation.

Rules:
- Do not answer the query.
- Do not invent data.
- Preserve invoice numbers exactly.
- Preserve HSN numbers exactly.
- Preserve dates exactly.
- Preserve amounts exactly.
- Preserve company/customer/vendor names exactly.
- Convert the business meaning into simple English.
- Keep the user's intent unchanged.

MULTI-INTENT RULES:
- If the user asks multiple things joined by aur/and/ane/also, preserve all intents.
- Do not drop any part of the query.
- If the query contains both invoice/bill and product/HSN/stock, set document_type to "mixed".
- If the query contains sales + purchase, set document_type to "mixed".
- If the query only says bill/invoice and does not clearly say sales or purchase, set document_type to "unknown_invoice".

ERP mappings:
sales bill / sale bill / bikri bill = sales invoice
purchase bill / kharidi bill = purchase invoice
customer / grahak / party = customer
vendor / supplier = vendor
amount / rakam / paisa / total = net amount
baki / pending / due = outstanding amount
status / paid / unpaid / pending = status
stock / quantity / qty = closing quantity
kam / less / niche / ochhi / ochhu = less than
zyada / vadhu / upar = greater than
dikhao / batao / batavo / dakhvo / dakhva = show

Output format:
{
  "canonical_query": "...",
  "language": "english|hindi|hinglish|gujarati|mixed",
  "confidence": "high|medium|low"
}

Examples:

User:
A/0326/C0077 sales bill ka customer name, amount aur status batao

Output:
{
  "canonical_query": "Show customer name, net amount and status for sales invoice A/0326/C0077",
  "document_type": "sales_invoice",
  "language": "hinglish",
  "confidence": "high"
}

User:
PR-31 purchase bill ka vendor name aur net amount dikhao

Output:
{
  "canonical_query": "Show vendor name and net amount for purchase invoice PR-31",
  "document_type": "purchase_invoice",
  "language": "hinglish",
  "confidence": "high"
}

User:
A/0326/C0077 wale bill me kitna baqaya paisa reh gaya hai aur bill ki stithi kya hai?

Output:
{
  "canonical_query": "Show outstanding amount and status for invoice A/0326/C0077",
  "document_type": "unknown_invoice",
  "language": "hinglish",
  "confidence": "medium"
}

User:
HSN 48211090 ke saman me jiska bacha hua stock shunya se kam hai, uska naam aur matra batao

Output:
{
  "canonical_query": "Show product name, HSN and closing quantity for products with HSN 48211090 where closing quantity is less than 0",
  "document_type": "product",
  "language": "hindi",
  "confidence": "high"
}

User:
A/0326/C0077 bill ka customer amount bata aur HSN 00000000 ka product dikha

Output:
{
  "canonical_query": "Show customer name and net amount for invoice A/0326/C0077 and show product details for HSN 00000000",
  "document_type": "mixed",
  "language": "hinglish",
  "confidence": "high"
}

User:
A/0326/C0077 kiska bill hai?

Output:
{
  "canonical_query": "Show party name for invoice A/0326/C0077",
  "document_type": "unknown_invoice",
  "language": "hinglish",
  "confidence": "medium"
}

User:
jo jo customers ko hamne sell kia hai unsabke name chaia

Output:
{
  "canonical_query": "Show names of all customers to whom we have sold items",
  "document_type": "sales_invoice",
  "language": "hinglish",
  "confidence": "high"
}

User:
hamare sare goods ka list chaia

Output:
{
  "canonical_query": "Show list of all products or goods",
  "document_type": "product",
  "language": "hinglish",
  "confidence": "high"
}
"""


def needs_canonicalization(query: str) -> bool:
    q = query.lower()

    multilingual_words = {
        "ka", "ke", "ki", "ko", "se", "me", "mein",
        "aur", "ane", "ani",
        "batao", "batavo", "dikhao", "dakhvo", "dakhva",
        "kitna", "kitni", "kya",
        "rakam", "paisa", "baki",
        "kam", "zyada", "vadhu", "ochhi", "ochhu",
        "grahak", "maal", "chhe", "che",
        "wala", "wale", "jiska", "jinki", "jisme"
    }

    words = set(re.sub(r"[^\w/.-]+", " ", q).split())
    return bool(words & multilingual_words)


def extract_json_object(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return {}

    try:
        return json.loads(match.group(0))
    except Exception:
        return {}

@traceable(name="canonicalizer_node", run_type="chain")
async def canonicalizer_node(state: MainState) -> MainState:
    try:
        print("Canonicalizer node triggered")

        user_query = state.get("user_query", "")
        
        if not user_query:
            return {
                "canonical_query": "",
                "canonicalizer_used": False,
                "canonicalizer_confidence": "low",
                "detected_language": "unknown",
            }

        if not needs_canonicalization(user_query):
            print("Canonicalizer skipped: query looks English")
            return {
                "canonical_query": user_query,
                "canonicalizer_used": False,
                "canonicalizer_confidence": "high",
                "detected_language": "english",
            }

        response = await normalizer_llm.ainvoke([
            SystemMessage(content=CANONICALIZER_PROMPT),
            HumanMessage(content=user_query)
        ])

        data = extract_json_object(response.content)

        canonical_query = data.get("canonical_query") or user_query
        language = data.get("language", "mixed")
        confidence = data.get("confidence", "medium")

        print("Original query:", user_query)
        print("Canonical query:", canonical_query)
        print("Detected language:", language)
        print("Canonicalizer confidence:", confidence)

        return {
            "canonical_query": canonical_query,
            "canonicalizer_used": True,
            "canonicalizer_confidence": confidence,
            "detected_language": language,
            "document_type": data.get("document_type", "unknown")
        }

    except Exception as e:
        print(f"Canonicalizer failed: {e}")
        return {
            "canonical_query": state.get("user_query", ""),
            "canonicalizer_used": False,
            "canonicalizer_confidence": "low",
            "detected_language": "unknown",
        }
def keyword_tool_override(query: str) -> list[str]:
    q = query.lower()
    selected_tools = []

    sales_keywords = [
        "sales invoice",
        "sale invoice",
        "sales bill",
        "sale bill",
        "customer invoice",
        "customer bill",
        "sales",
        "sale",
        "bikri",
        "bikri invoice",
        "bikri bill",
    ]

    purchase_keywords = [
        "purchase invoice",
        "purchase bill",
        "vendor bill",
        "supplier bill",
        "purchase",
        "khareedi",
        "kharidi",
        "khareedi invoice",
        "kharidi invoice",
    ]

    product_keywords = [
        "product",
        "products",
        "inventory",
        "stock",
        "hsn",
        "sku",
        "item",
        "items",
        "gst rate",
    ]

    if any(word in q for word in sales_keywords):
        selected_tools.append("get_sales_list")

    if any(word in q for word in purchase_keywords):
        selected_tools.append("get_purchase_list")

    if any(word in q for word in product_keywords):
        selected_tools.append("get_product_list")

    return selected_tools

def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def split_query_parts(query: str) -> list[str]:
    """
    Splits multi-intent queries without being too aggressive.
    Example:
    sales bill ... aur HSN ... product dikha
    """
    if not query:
        return []

    separators = [
        ";",
        " and ",
        " aur ",
        " ane ",
        " ani ",
        " also ",
        " plus ",
    ]

    parts = [query]

    for sep in separators:
        new_parts = []
        for part in parts:
            new_parts.extend(part.split(sep))
        parts = new_parts

    return [p.strip() for p in parts if p.strip()]


def score_tool_from_metadata(query_part: str, tool_meta: dict) -> int:
    q = normalize_text(query_part)
    score = 0

    for alias in tool_meta.get("aliases", []):
        alias_l = alias.lower()
        if alias_l in q:
            score += 5

    for field, aliases in tool_meta.get("field_aliases", {}).items():
        for alias in aliases:
            alias_l = alias.lower()
            if alias_l in q:
                score += 2

    # Light description matching
    description = normalize_text(tool_meta.get("description", ""))
    for word in q.split():
        if len(word) > 3 and word in description:
            score += 1

    return score


def select_tools_from_metadata_for_part(
    query_part: str,
    registry: dict,
    min_score: int = 2,
) -> list[str]:
    scored = []

    for tool_name, meta in registry.items():
        score = score_tool_from_metadata(query_part, meta)

        if score >= min_score:
            scored.append((tool_name, score))

    scored.sort(key=lambda item: item[1], reverse=True)

    return [tool_name for tool_name, score in scored]


def merge_unique_tools(tool_lists: list[list[str]]) -> list[str]:
    merged = []

    for tools in tool_lists:
        for tool_name in tools:
            if tool_name not in merged:
                merged.append(tool_name)

    return merged


def get_tools_by_category(registry: dict, category: str) -> list[str]:
    tools = []

    for tool_name, meta in registry.items():
        if meta.get("category") == category:
            tools.append(tool_name)

    return tools
# ============================================
# SEMANTIC SEARCH NODE
# ============================================

@traceable(name="semantic_search_node", run_type="retriever")
async def semantic_search(state: MainState) -> MainState:
    try:
        print("Semantic search node triggered")

        original_query = state.get("user_query", "") or ""
        canonical_query = state.get("canonical_query", "") or ""
        document_type = (state.get("document_type", "") or "").lower().strip()

        user_query = canonical_query or original_query
        combined_query = f"{original_query} {canonical_query}".strip()

        if not user_query:
            return {
                "retrieved_tools": [],
                "selected_tools": [],
                "query_parts": [],
                "skip_router": True,
            }

        print(f"Original query: {original_query}")
        print(f"Canonical query: {canonical_query}")
        print(f"Document type: {document_type}")

        selected_tool_groups = []

        # -------------------------------------------------
        # 1. Use canonicalizer document_type generically
        # -------------------------------------------------
        if document_type == "unknown_invoice":
            # Dynamic: select all invoice-category tools from metadata
            selected_tool_groups.append(
                get_tools_by_category(TOOL_INTENT_REGISTRY, "invoice")
            )

        elif document_type == "sales_invoice":
            selected_tool_groups.append(["get_sales_list"])

        elif document_type == "purchase_invoice":
            selected_tool_groups.append(["get_purchase_list"])

        elif document_type == "product":
            selected_tool_groups.append(["get_product_list"])

        # For mixed, do not decide here.
        # Let query part matching below select tools.
        elif document_type == "mixed":
            pass

        # -------------------------------------------------
        # 2. Split multi-intent query and match each part
        # -------------------------------------------------
        query_parts = split_query_parts(combined_query)

        if not query_parts:
            query_parts = [user_query]

        print(f"Query parts for metadata matching: {query_parts}")

        for part in query_parts:
            tools_for_part = select_tools_from_metadata_for_part(
                part,
                TOOL_INTENT_REGISTRY,
                min_score=2,
            )

            if tools_for_part:
                print(f"Metadata tools for part '{part}': {tools_for_part}")
                selected_tool_groups.append(tools_for_part)

        selected_tools = merge_unique_tools(selected_tool_groups)

        # -------------------------------------------------
        # 3. If metadata found tools, return them
        # -------------------------------------------------
        if selected_tools:
            print(f"Final metadata selected tools: {selected_tools}")

            return {
                "retrieved_tools": selected_tools,
                "selected_tools": selected_tools,
                "query_parts": query_parts,
                # Skip router because metadata already merged tools.
                # Router may drop one tool again.
                "skip_router": True,
            }

        # -------------------------------------------------
        # 4. Fallback vector search
        # -------------------------------------------------
        print("No metadata match. Falling back to vector search.")

        retrieved_tools = await retriever(user_query)
        tool_names = [tool.name for tool in retrieved_tools]

        print(f"Vector retrieved tools: {tool_names}")

        return {
            "retrieved_tools": tool_names,
            "selected_tools": tool_names,
            "query_parts": query_parts,
            "skip_router": False,
        }

    except Exception as e:
        print(f"Error in semantic search node: {e}")

        return {
            "retrieved_tools": [],
            "selected_tools": [],
            "query_parts": [],
            "skip_router": True,
        }

# ============================================
# SYSTEM PROMPT
# ============================================
def build_system_prompt(
    user_query: str,
    selected_tools: list[str],
    query_parts: list[str] | None = None
) -> str:
    prompt = """
/no_think
You are an ERP tool-call worker.

CRITICAL:
Use actual bound tool_calls only.
No text. No markdown. No JSON explanation. No final answer.

QUERY:
__USER_QUERY__

TOOLS:
__SELECTED_TOOLS__

TASK:
Call every required tool from TOOLS.
For multi-part queries, call all needed tools in one response.
Never stop after the first tool.
Never invent records, tools, fields, filters, dates, or ledger IDs.

ARGS:
term = search value.
filters = exact JSON filters.
fields = output columns.

FIELDS:
Invoice: invoiceNo, invoiceDate, billToName, billToState, billToCity, netAmount, outstanding, status, taxableAmount, igstAmount, cgstAmount, sgstAmount.
Product: name, sku, hsn, closingQty, closingRate, igst, cgst, sgst, uom.

MAPPING:
customer/vendor/supplier/party -> billToName
amount/net/total -> netAmount
pending/due/outstanding/baki -> outstanding
GST/tax/breakup -> taxableAmount, igstAmount, cgstAmount, sgstAmount
stock/qty/quantity/closing quantity -> closingQty
product/item -> name

FILTERS:
invoice X -> term=X, filters={"invoiceNo": X}
HSN X -> term=X, filters={"hsn": X}
state X -> filters={"billToState": X}
status X -> filters={"status": X}
amount > N -> filters={"netAmount":{"gt":N}}
outstanding > N -> filters={"outstanding":{"gt":N}}
closing quantity < N -> filters={"closingQty":{"lt":N}}

ALL/LIST RULES:
- "all", "sare", "sab", "unsabke", "jo jo", "list" means return multiple records.
- Do not use limit=1.
- Use limit=50 unless user asks for a specific number.
- If user asks for customer/vendor/supplier names only, fields=["billToName"].
- If user asks for product/goods/item list, fields=["name","sku","hsn"].
- If TOOLS contains multiple tools, call all required tools.
- For multi-part queries, create one tool call for each relevant tool.
- Do not stop after one tool call.

SAME-TOOL MULTI-INTENT RULE:

If the user asks multiple independent requests that require the same tool with different filters, call the same tool multiple times.

Do not merge different filters into one call.
Do not drop the second same-tool request.

Example:
User asks:
"48211090 HSN negative stock dikha aur HSN 00000000 product check kar"

Correct tool calls:
1. get_product_list with filters {"hsn": "48211090", "closingQty": {"lt": 0}}
2. get_product_list with filters {"hsn": "00000000"}

Incorrect:
Only calling get_product_list for HSN 48211090.
Every independent query part joined by ";", "aur", "and", "ane", or "also" must be satisfied.
Each part must result in either:
- a tool call with matching filters, or
- an empty result section after tool execution.
STRICT:
Always include fields.
Invoice query: include invoiceNo.
Product/HSN query: include name and hsn.
Filter fields must appear in fields.
Do not use limit=1 unless user asks one/latest/top.
PR-31 can have multiple records; return all matches.
Full/raw/all details -> fields=[].

LANG:
aur/ane/ani = and
zyada/vadhu/upar = gt
kam/ochhi/niche/less than = lt
dikhao/bata/batavo/dakhva/show = show

FINAL:
Actual tool_calls only.
"""

    return (
        prompt
        .replace("__USER_QUERY__", user_query)
        .replace("__SELECTED_TOOLS__", str(selected_tools))
    )



def now():
    return time.perf_counter()


def sec(start):
    return round(time.perf_counter() - start, 3)


def ns_to_sec(value):
    if value is None:
        return None
    try:
        return round(value / 1_000_000_000, 3)
    except Exception:
        return value


def print_ollama_metadata(response):
    metadata = getattr(response, "response_metadata", {}) or {}

    print("\n========== OLLAMA METADATA ==========")
    print("model:", metadata.get("model"))
    print("done_reason:", metadata.get("done_reason"))

    print("total_duration:", ns_to_sec(metadata.get("total_duration")), "sec")
    print("load_duration:", ns_to_sec(metadata.get("load_duration")), "sec")
    print("prompt_eval_duration:", ns_to_sec(metadata.get("prompt_eval_duration")), "sec")
    print("eval_duration:", ns_to_sec(metadata.get("eval_duration")), "sec")

    print("prompt_eval_count:", metadata.get("prompt_eval_count"))
    print("eval_count:", metadata.get("eval_count"))
    print("=====================================\n")

@traceable(name="chat_model_node", run_type="llm")
async def chat_model_node(state: MainState):
    node_start = now()

    try:
        print("\n========== CHAT MODEL NODE START ==========")

        step = now()
        # user_query = state.get("user_query", "")
        original_query = state.get("user_query", "")
        user_query = state.get("canonical_query") or original_query
        messages = state.get("messages", [])
        # selected_tools = state.get("selected_tools") or state.get("retrieved_tools", [])
        selected_tools = state.get("selected_tools", [])
        query_parts = state.get("query_parts", [user_query])
        loop_count = state.get("loop_count", 0)

        print(f"[1] Read state: {sec(step)}s")
        print("user_query:", user_query)
        print("selected_tools:", selected_tools)
        print("query_parts:", query_parts)
        print("loop_count:", loop_count)

        step = now()
        available_tools = [
            tools_dict[name]
            for name in selected_tools
            if name in tools_dict
        ]

        print(f"[2] Loaded available tools: {sec(step)}s")
        print("available_tool_names:", [tool.name for tool in available_tools])

        if not available_tools:
            print("[CHAT MODEL] No available tools. Ending safely.")
            return {
                "messages": messages + [
                    AIMessage(content="No available tools for this query.")
                ],
                "loop_count": loop_count + 1,
            }

        step = now()
        if len(available_tools) == 1:
            llm_with_tools = llm.bind_tools(
                available_tools,
                tool_choice=available_tools[0].name
            )
        else:
            llm_with_tools = llm.bind_tools(available_tools)
        print(f"[3] Bound tools to LLM: {sec(step)}s")

        step = now()
        system_prompt = build_system_prompt(
            user_query=user_query,
            selected_tools=selected_tools,
            query_parts=query_parts
        )
        print(f"[4] Built system prompt: {sec(step)}s")
        print("system_prompt_chars:", len(system_prompt))

        step = now()
        if not messages:
            messages = [HumanMessage(content=user_query)]

        llm_input = [
            SystemMessage(content=system_prompt),
            *messages
        ]

        print(f"[5] Built LLM input messages: {sec(step)}s")
        print("message_count:", len(llm_input))
        print("message_types:", [type(m).__name__ for m in llm_input])

        step = now()
        print("[6] Invoking LLM...")
        response = await llm_with_tools.ainvoke(llm_input)
        print(f"[6] LLM invoke completed: {sec(step)}s")
        print("\n========== RAW WORKER RESPONSE DEBUG ==========")
        print("response_type:", type(response).__name__)
        print("content:", repr(getattr(response, "content", "")))
        print("tool_calls:", getattr(response, "tool_calls", None))
        print("additional_kwargs:", getattr(response, "additional_kwargs", {}))
        print("response_metadata:", getattr(response, "response_metadata", {}))
        print("==============================================\n")
        print_ollama_metadata(response)

        content = getattr(response, "content", "")
        tool_calls = getattr(response, "tool_calls", []) or []

        print("\n========== WORKER LLM RESPONSE ==========")
        print("response_type:", type(response).__name__)
        print("content:", repr(content))
        print("tool_call_count:", len(tool_calls))
        print("tool_calls:", tool_calls)
        print("========================================\n")

        for i, call in enumerate(tool_calls, start=1):
            print(f"\n--- Tool Call {i} ---")
            print("name:", call.get("name"))
            print("args:")
            print(json.dumps(call.get("args", {}), indent=2, ensure_ascii=False))

        print(f"[TOTAL chat_model_node]: {sec(node_start)}s")
        print("========== CHAT MODEL NODE END ==========\n")

        return {
            "messages": messages + [response],
            "loop_count": loop_count + 1,
        }

    except Exception as e:
        print(f"[CHAT MODEL ERROR]: {e}")
        print(f"[TOTAL chat_model_node before error]: {sec(node_start)}s")

        return {
            "messages": state.get("messages", []) + [
                AIMessage(content=f"Chat model error: {str(e)}")
            ],
            "loop_count": state.get("loop_count", 0) + 1,
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


def dedupe_records_by_field(records: list[dict], field: str) -> list[dict]:
    """
    Removes duplicate records based on one field.
    Example: billToName for customer/vendor name list queries.
    """
    if not isinstance(records, list):
        return records

    seen = set()
    deduped = []

    for record in records:
        if not isinstance(record, dict):
            continue

        value = record.get(field)

        if value is None or str(value).strip() == "":
            continue

        key = str(value).strip().lower()

        if key in seen:
            continue

        seen.add(key)
        deduped.append(record)

    return deduped


def wants_unique_party_names(query: str) -> bool:
    """
    Detects user intent like:
    - all customer names
    - all vendors
    - jinse kharidi ki hai un sab ka name
    - jo jo customers ko sell kia hai
    """
    q = (query or "").lower()

    party_words = [
        "customer", "customers",
        "vendor", "vendors",
        "supplier", "suppliers",
        "party", "parties",
        "grahak",
        "khareedaar",
        "vikreta",
        "aapurti",
        "jinse",
        "jisko",
        "jinko",
    ]

    name_words = [
        "name", "names",
        "naam",
        "nam",
    ]

    list_words = [
        "all",
        "list",
        "sare",
        "saare",
        "sab",
        "un sab",
        "unsab",
        "unsabke",
        "jo jo",
        "badha",
        "badha aapje",
        "chaia",
        "chahiye",
        "chaiye",
    ]

    has_party_word = any(word in q for word in party_words)
    has_name_word = any(word in q for word in name_words)
    has_list_word = any(word in q for word in list_words)

    return has_party_word and has_name_word and has_list_word


def apply_final_postprocessing(
    final_data: dict,
    original_query: str,
    canonical_query: str = "",
) -> dict:
    """
    Final deterministic cleanup after tools return data.
    This should not invent data.
    It only cleans/organizes existing tool results.
    """
    if not isinstance(final_data, dict):
        return final_data

    combined_query = f"{original_query or ''} {canonical_query or ''}".strip()

    if wants_unique_party_names(combined_query):
        if "get_sales_list" in final_data:
            final_data["get_sales_list"] = dedupe_records_by_field(
                final_data["get_sales_list"],
                "billToName",
            )

        if "get_purchase_list" in final_data:
            final_data["get_purchase_list"] = dedupe_records_by_field(
                final_data["get_purchase_list"],
                "billToName",
            )

    return final_data

# ============================================
# DETERMINISTIC FINAL NODE
# ============================================
@traceable(name="deterministic_final_node", run_type="chain")
async def deterministic_final_node(state: MainState):
    """
    Builds final JSON using Python, not LLM.
    This removes the second LLM call.
    """

    user_query = state.get("user_query", "")
    canonical_query = state.get("canonical_query", "")
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

    # -------------------------------------------------
    # NEW: final deterministic cleanup
    # Example: dedupe customer/vendor names for list queries
    data = apply_final_postprocessing(
    data,
    user_query,
    canonical_query,
)

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




#A new router node is being added since we will use the new router llm which is a small llm and we will use it to do our basic work that way we can make 
# a more simpler prompt for our main llm
@traceable(name="router_node", run_type="chain")
async def router_node(state: MainState):
    """
    Small model router:
    - Receives user query
    - Receives tools retrieved by semantic search
    - Selects only required tools
    - Does NOT answer the user
    """

    print("Router node called")

    user_query = state.get("user_query", "")
    retrieved_tools = state.get("retrieved_tools", [])

    if not retrieved_tools:
        return {
            "router_decision": {
                "route": "unsupported",
                "required_tools": [],
                "query_parts": [user_query],
                "confidence": 0.0,
                "reason": "No tools were retrieved."
            },
            "selected_tools": [],
            "query_parts": [user_query]
        }

    router_prompt = """
You are a strict ERP/accounting router.

USER QUERY:
__USER_QUERY__

AVAILABLE TOOLS:
__RETRIEVED_TOOLS__

JOB:
Select required tools only from AVAILABLE TOOLS.
Do not answer. Do not call tools. Return only raw JSON.

JSON FORMAT:
{
  "route": "tool_worker",
  "required_tools": [],
  "query_parts": [],
  "confidence": 0.0,
  "reason": ""
}

RULES:
- required_tools must only contain names from AVAILABLE TOOLS.
- Multi-part ERP query => select all matching tools.
- sales/customer bills -> get_sales_list
- purchase/vendor/supplier bills -> get_purchase_list
- products/inventory/stock/HSN/SKU/GST -> get_product_list
- If no available tool can answer, use route "unsupported" and required_tools=[].
- Never invent tool names.
"""

    router_prompt = (
        router_prompt
        .replace("__USER_QUERY__", user_query)
        .replace("__RETRIEVED_TOOLS__", str(retrieved_tools))
    )

    messages = [
        SystemMessage(content=router_prompt),
        HumanMessage(content=user_query)
    ]

    try:
        response = await router_llm.ainvoke(messages)
        decision = json.loads(response.content)

    except Exception as e:
        print(f"Router parse/error fallback: {e}")

        decision = {
            "route": "tool_worker",
            "required_tools": retrieved_tools,
            "query_parts": [user_query],
            "confidence": 0.5,
            "reason": "Router failed, falling back to retrieved tools."
        }

    route = decision.get("route", "tool_worker")
    required_tools = decision.get("required_tools", [])

    if route == "unsupported":
        selected_tools = []
    else:
        selected_tools = [
            tool_name
            for tool_name in required_tools
            if tool_name in retrieved_tools
        ]

        if not selected_tools:
            selected_tools = retrieved_tools

    print("Router selected tools:", selected_tools)

    return {
        "router_decision": decision,
        "selected_tools": selected_tools,
        "query_parts": decision.get("query_parts", [user_query])
    }