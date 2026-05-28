from src.schema import MainState
from src.retriever import retriever
from src.tools_api import tools_dict, tools
from src.tool_doc import TOOL_INTENT_REGISTRY
from src.config import llm, normalizer_llm
import time
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langgraph.prebuilt import ToolNode
import json
import re
from langsmith import traceable


def now():
    return time.perf_counter()
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
def is_plain_english_query(query: str) -> bool:
    """
    Returns True when the query looks like normal English.
    Mixed Hindi/Gujarati/Marathi slang should return False
    so canonicalizer can normalize it.
    """

    q = query.lower().strip()

    if not q:
        return True

    # Detect Devanagari/Gujarati script characters
    for char in q:
        code = ord(char)

        # Devanagari block: Hindi/Marathi
        if 0x0900 <= code <= 0x097F:
            return False

        # Gujarati block
        if 0x0A80 <= code <= 0x0AFF:
            return False

    non_english_hints = [
        "batao",
        "batavo",
        "dikhao",
        "dakhva",
        "joiye",
        "batana",
        "ka",
        "ke",
        "ki",
        "no",
        "nu",
        "na",
        "ane",
        "aur",
        "ani",
        "wala",
        "wale",
        "jisme",
        "jema",
        "madhle",
        "kam",
        "ochhi",
        "ochhu",
        "ochha",
        "zyada",
        "vadhu",
        "jast",
        "adhik",
        "baki",
        "thakbaki",
        "khata",
        "hisab",
        "jaththo",
        "satha",
    ]

    words = set(q.replace(",", " ").replace("?", " ").split())

    return not any(word in words for word in non_english_hints)

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


def is_routeable_without_canonicalizer(query: str) -> bool:
    """
    Returns True when the query already contains enough ERP/tool-domain
    keywords for semantic_search to route it without normalizer_llm.

    This is tool-level routing only. It does not hardcode output columns.
    """
    q = re.sub(r"\s+", " ", (query or "").lower()).strip()

    route_keywords = [
        # customer domain
        "customer", "customer id", "party", "client", "buyer", "grahak",
        "opening balance", "opening type",

        # ledger domain
        "ledger", "account statement", "statement", "transactions",
        "closing balance", "current balance", "khata", "hisab",

        # stock/product domain
        "stock", "inventory", "product", "products", "item", "items",
        "hsn", "hsn code", "sku", "closing quantity", "closing qty",
        "low stock", "out of stock", "maal", "jaththo", "satha",


        #GST
        "gst",
"gst summary",
"gst report",
"b2b",
"b2c",
"igst",
"cgst",
"sgst",
"tds",
"tcs",
    ]

    return any(keyword in q for keyword in route_keywords)


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
    """
    Canonicalizes only when needed.

    Fast path:
    - Plain English queries skip canonicalizer.
    - ERP queries that are already routeable by keyword/domain skip canonicalizer,
      even if they contain Hinglish words like batao/aur/ka.

    Slow path:
    - Ambiguous multilingual queries use normalizer_llm.
    """
    try:
        print("Canonicalizer node triggered")

        user_query = state.get("user_query", "") or ""

        if not user_query:
            return {
                "original_query": "",
                "canonical_query": "",
                "user_query": "",
                "canonicalizer_used": False,
                "canonicalizer_confidence": "low",
                "detected_language": "unknown",
                "document_type": "unknown",
            }

        if is_plain_english_query(user_query):
            print("Canonicalizer skipped: query looks English")
            return {
                "original_query": user_query,
                "canonical_query": user_query,
                "user_query": user_query,
                "canonicalizer_used": False,
                "canonicalizer_confidence": "skipped_english",
                "detected_language": "english",
                "document_type": "routeable",
            }

        if is_routeable_without_canonicalizer(user_query):
            print("Canonicalizer skipped: query is directly routeable by ERP keywords")
            return {
                "original_query": user_query,
                "canonical_query": user_query,
                "user_query": user_query,
                "canonicalizer_used": False,
                "canonicalizer_confidence": "skipped_routeable",
                "detected_language": "mixed_or_english",
                "document_type": "routeable",
            }

        if not needs_canonicalization(user_query):
            print("Canonicalizer skipped: no multilingual normalization needed")
            return {
                "original_query": user_query,
                "canonical_query": user_query,
                "user_query": user_query,
                "canonicalizer_used": False,
                "canonicalizer_confidence": "skipped_no_normalization_needed",
                "detected_language": "english_or_mixed",
                "document_type": "unknown",
            }

        response = await normalizer_llm.ainvoke([
            SystemMessage(content=CANONICALIZER_PROMPT),
            HumanMessage(content=user_query),
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
            "original_query": user_query,
            "canonical_query": canonical_query,
            "user_query": canonical_query,
            "canonicalizer_used": True,
            "canonicalizer_confidence": confidence,
            "detected_language": language,
            "document_type": data.get("document_type", "unknown"),
        }

    except Exception as e:
        print(f"Canonicalizer failed: {e}")
        user_query = state.get("user_query", "") or ""
        return {
            "original_query": user_query,
            "canonical_query": user_query,
            "user_query": user_query,
            "canonicalizer_used": False,
            "canonicalizer_confidence": "low",
            "detected_language": "unknown",
            "document_type": "unknown",
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

def add_unique(items: list[str], value: str):
    """Append a tool name only once while preserving order."""
    if value and value not in items:
        items.append(value)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()



def is_unsupported_current_scope(query: str) -> bool:
    """
    Current prototype supports only 6 tools:
    customer, customer ledger, stock levels, GST summary, TDS outstanding, TCS outstanding.
    Invoice/voucher tools are not enabled, so fail fast instead of guessing customer/stock.
    """
    q = normalize_text(query)

    unsupported_hints = [
        "sales invoice", "sale invoice", "sales bill", "sale bill",
        "purchase invoice", "purchase bill", "vendor bill", "supplier bill",
        "receipt voucher", "payment voucher",
        "invoice no", "invoice number", "voucher no", "voucher number",
    ]

    return any(hint in q for hint in unsupported_hints)


def split_query_parts(query: str) -> list[str]:
    """
    Splits one query into intent parts.
    Kept for backward compatibility, but semantic_search now uses
    split_query_for_tools() so original and canonical queries are not
    concatenated before splitting.
    """
    if not query:
        return []

    split_pattern = (
        r"\s+aur\s+|"
        r"\s+ane\s+|"
        r"\s+ani\s+|"
        r"\s+also\s+|"
        r"\s+and\s+|"
        r"\s+plus\s+|"
        r";\s*"
    )

    return [
        part.strip()
        for part in re.split(split_pattern, query, flags=re.IGNORECASE)
        if part.strip()
    ]


def split_query_for_tools(original_query: str, canonical_query: str = "") -> list[str]:
    """
    Split original and canonical query separately.

    Important: do NOT concatenate original + canonical before splitting.
    Concatenation created broken parts such as:
    'closing quantity dikhao Show Nykaa Bangalore customer ID'
    """
    parts: list[str] = []

    for query in [original_query, canonical_query]:
        for part in split_query_parts(query):
            if part and part not in parts:
                parts.append(part)

    return parts or [original_query or canonical_query]


def score_tool_from_metadata(query_part: str, tool_meta: dict) -> int:
    q = normalize_text(query_part)
    score = 0

    for alias in tool_meta.get("aliases", []):
        alias_l = str(alias).lower()
        if alias_l and alias_l in q:
            score += 5

    for keyword in tool_meta.get("keywords", []):
        keyword_l = str(keyword).lower()
        if keyword_l and keyword_l in q:
            score += 4

    for field in tool_meta.get("fields", []):
        field_l = str(field).lower()
        if field_l and field_l in q:
            score += 2

    # Supports both shapes:
    #   {"field": ["alias1", "alias2"]}
    #   {"alias phrase": "field"}
    for key, value in tool_meta.get("field_aliases", {}).items():
        candidates = [key]
        if isinstance(value, list):
            candidates.extend(value)
        elif isinstance(value, str):
            candidates.append(value)

        for alias in candidates:
            alias_l = str(alias).lower()
            if len(alias_l) > 1 and alias_l in q:
                score += 2

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
    merged: list[str] = []

    for tool_group in tool_lists:
        for tool_name in tool_group:
            add_unique(merged, tool_name)

    return merged


def get_tools_by_category(registry: dict, category: str) -> list[str]:
    matched_tools = []

    for tool_name, meta in registry.items():
        if meta.get("category") == category:
            matched_tools.append(tool_name)

    return matched_tools


def keyword_tools_for_part(part: str) -> list[str]:
    """
    Tool-domain keyword override.

    This is intentionally NOT column-specific hardcoding. It only decides
    which high-level tool/domain is needed. Field selection remains dynamic
    in the worker prompt/tool args.
    """
    q = normalize_text(part)
    selected: list[str] = []

    customer_hints = [
        "customer", "customer id", "party", "client", "buyer", "grahak",
        "ledger name", "opening balance", "opening type",
    ]

    ledger_hints = [
        "ledger", "account statement", "statement", "transactions",
        "closing balance", "current balance", "khata", "hisab",
    ]

    stock_hints = [
        "stock", "inventory", "product", "products", "item", "items",
        "hsn", "hsn code", "sku", "closing quantity", "closing qty",
        "low stock", "out of stock", "maal", "jaththo", "satha",
    ]
    gst_hints = [
        "gst",
        "gst summary",
        "gst report",
        "gstr",
        "b2b",
        "b2c",
        "exports",
        "nil rated",
        "exempted",
        "igst",
        "cgst",
        "sgst",
        "cess",
        "taxable amount",
        "invoice amount",
        "voucher count",
    ]

    tds_hints = [
        "tds",
        "tds outstanding",
        "tds payable",
        "tds pending",
        "tds report",
        "194c",
        "194j",
        "194i",
    ]

    tcs_hints = [
        "tcs",
        "tcs outstanding",
        "tcs payable",
        "tcs pending",
        "tcs report",
        "206c",
    ]

    if any(word in q for word in gst_hints):
        add_unique(selected, "get_gst_summary")

    if any(word in q for word in tds_hints):
        add_unique(selected, "get_tds_outstanding")

    if any(word in q for word in tcs_hints):
        add_unique(selected, "get_tcs_outstanding")

    has_customer = any(word in q for word in customer_hints)
    has_ledger = any(word in q for word in ledger_hints)
    has_stock = any(word in q for word in stock_hints)

    if has_customer and not has_ledger:
        add_unique(selected, "get_customer")

    if has_ledger:
        direct_customer_id = bool(
            re.search(r"\bcustomer\s*id\s*[:#-]?\s*\d+\b", q)
            or re.search(r"\bcustomer_id\s*[:#-]?\s*\d+\b", q)
        )

        if not direct_customer_id:
            add_unique(selected, "get_customer")

        add_unique(selected, "get_customer_ledger")

    if has_stock:
        add_unique(selected, "get_stock_levels")

    return selected
    

def is_multi_intent_query(original_query: str, canonical_query: str, query_parts: list[str]) -> bool:
    combined = f"{original_query or ''} {canonical_query or ''}".lower()

    connectors = [
        " aur ", " ane ", " ani ", " also ", " and ", ";",
    ]

    if any(connector in combined for connector in connectors):
        return True

    return len(query_parts) > 1
# ============================================
# SEMANTIC SEARCH NODE
# ============================================

@traceable(name="semantic_search_node", run_type="retriever")
async def semantic_search(state: MainState) -> MainState:
    try:
        print("Semantic search node triggered")

        original_query = state.get("original_query") or state.get("user_query", "") or ""
        canonical_query = state.get("canonical_query", "") or ""
        document_type = (state.get("document_type", "") or "").lower().strip()

        user_query = canonical_query or original_query

        if not user_query:
            return {
                "retrieved_tools": [],
                "selected_tools": [],
                "query_parts": [],
                "skip_router": True,
            }

        if is_unsupported_current_scope(user_query):
            print("Unsupported query for current 6-tool scope. Skipping tool calls.")
            return {
                "retrieved_tools": [],
                "selected_tools": [],
                "query_parts": [user_query],
                "skip_router": True,
                "unsupported": True,
                "unsupported_reason": "This query needs invoice/voucher tools, which are not enabled in the current 6-tool scope.",
            }

        print(f"Original query: {original_query}")
        print(f"Canonical query: {canonical_query}")
        print(f"Document type: {document_type}")

        query_parts = split_query_for_tools(
            original_query=original_query,
            canonical_query=canonical_query,
        )

        if not query_parts:
            query_parts = [user_query]

        print(f"Query parts for metadata matching: {query_parts}")

        selected_tool_groups: list[list[str]] = []
        used_keyword_routing = False

        # -------------------------------------------------
        # 1. Keyword/tool-domain routing first.
        # If keyword routing finds a clear tool for a part,
        # do not also run metadata for the same part because
        # metadata can over-select noisy tools.
        # -------------------------------------------------
        for part in query_parts:
            keyword_selected = keyword_tools_for_part(part)

            if keyword_selected:
                print(f"Keyword tools for part '{part}': {keyword_selected}")
                selected_tool_groups.append(keyword_selected)
                used_keyword_routing = True
                continue

            tools_for_part = select_tools_from_metadata_for_part(
                part,
                TOOL_INTENT_REGISTRY,
                min_score=3,
            )

            if tools_for_part:
                print(f"Metadata tools for part '{part}': {tools_for_part}")
                selected_tool_groups.append(tools_for_part)

        # -------------------------------------------------
        # 2. Optional document_type hint from canonicalizer.
        # This is additive only and does not override keyword tools.
        # -------------------------------------------------
        if document_type in {"product", "inventory", "stock"}:
            selected_tool_groups.append(["get_stock_levels"])
        elif document_type in {"customer", "party"}:
            selected_tool_groups.append(["get_customer"])
        elif document_type in {"customer_ledger", "ledger"}:
            selected_tool_groups.append(["get_customer_ledger"])

        selected_tools = merge_unique_tools(selected_tool_groups)

        selected_tools = [
            tool_name for tool_name in selected_tools
            if tool_name in tools_dict
        ]

        if selected_tools:
            print(f"Final selected tools: {selected_tools}")

            return {
                "retrieved_tools": selected_tools,
                "selected_tools": selected_tools,
                "query_parts": query_parts,
                # Router LLM has been removed. Keep this key for compatibility.
                "skip_router": True,
            }

        # -------------------------------------------------
        # 3. Fail fast instead of vector-guessing random tools.
        # Re-enable vector fallback only after adding score thresholds.
        # -------------------------------------------------
        print("No confident tool match. Marking query unsupported.")

        return {
            "retrieved_tools": [],
            "selected_tools": [],
            "query_parts": query_parts,
            "skip_router": True,
            "unsupported": True,
            "unsupported_reason": "No supported ERP tool matched this query.",
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
    return """
Granite ERP tool-caller. Output tool_calls only; no text/markdown/final JSON. Use only bound tools. Call every tool needed by query, skip irrelevant bound tools. Never invent ids, dates, fields, filters, amounts, balances or records. Keep dates exact. fields=list[str]; filters=object; limit=10 unless all/more.

Tools: get_customer=customer/party id,name,opening. get_customer_ledger=ledger/statement/opening,current,closing,transactions by customer_id. get_stock_levels=stock/product/HSN/qty/low/out stock. get_gst_summary=GST/GSTR/B2B/B2C/export/nil/tax/invoice amount. get_tds_outstanding=TDS outstanding/section. get_tcs_outstanding=TCS outstanding/section.

Rules:
Customer+city=>search brand only, filter name contains CITY.
Ex Nykaa Bangalore customer id=>get_customer(search="Nykaa",fields=["id","name"],filters={"name":{"contains":"BANGALORE"}}).
Customer opening=>fields=["id","name","openingBalance","openingType"].
If query asks customer and stock, call both.
Ledger with customer id=>get_customer_ledger only. Ledger with name=>get_customer first if selected.
Ledger balance=>fields=["ledgerName","opening","current","closing","period"]. Transactions/statement=>include "transactions".
HSN X=>get_stock_levels(term=X,filters={"hsnCode":X},fields=["name","hsnCode","closingQty"]).
closing value=>include closingValue. closing qty <N or >N=>use closingQty lt/gt filter.
low stock=>low_stock_only=true. out stock=>filters={"isOutOfStock":true}.
GST category filters use category: B2B=b2b, B2C Large=b2cLarge, B2C Small=b2cSmall, exports=exports, nil/exempt=nillRated, total/grand total=grandTotal.
Single GST category=>filter category. Multiple GST categories=>do not use category filter; include requested fields and categories.
B2B GST taxable IGST CGST SGST invoice amount=>fields=["category","name","taxableAmount","igst","cgst","sgst","invoiceAmount"].
TDS/TCS section like 194C/194J/206C=>filters={"section":"194C"}.
""".strip()


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
        original_query = state.get("user_query", "")
        user_query = state.get("canonical_query") or original_query
        selected_tools = state.get("selected_tools", [])
        query_parts = state.get("query_parts", [user_query])
        loop_count = state.get("loop_count", 0)

        previous_messages = [
            msg for msg in state.get("messages", [])
            if not isinstance(msg, SystemMessage)
        ]

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
            reason = state.get("unsupported_reason", "No available tools for this query.")
            return {
                "messages": previous_messages + [
                    AIMessage(content=reason)
                ],
                "loop_count": loop_count + 1,
            }

        step = now()
        if len(available_tools) == 1:
            llm_with_tools = llm.bind_tools(
                available_tools,
                tool_choice=available_tools[0].name,
            )
        else:
            llm_with_tools = llm.bind_tools(available_tools)
        print(f"[3] Bound tools to LLM: {sec(step)}s")

        prompt_start = time.perf_counter()
        system_prompt_text = build_system_prompt(
            user_query=user_query,
            selected_tools=selected_tools,
            query_parts=query_parts,
        )
        prompt_duration = time.perf_counter() - prompt_start

        print(f"[4] Built system prompt: {prompt_duration:.3f}s")
        print("system_prompt_chars:", len(system_prompt_text))

        system_prompt = SystemMessage(content=system_prompt_text)

        llm_input = [
            system_prompt,
            HumanMessage(content=user_query),
        ]

        print(f"[5] Built LLM input messages: {sec(prompt_start)}s")
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
            "messages": [HumanMessage(content=user_query), response],
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
def infer_requested_fields(user_query: str, tool_name: str) -> list[str]:
    """
    Fallback projection only. Normal projection should come from tool args.
    This keeps final JSON compact and prevents accidental full/raw dumps.
    """
    q = (user_query or "").lower()

    if tool_name == "get_customer":
        fields = ["id", "name"]

        if "opening" in q or "opening balance" in q:
            fields.extend(["openingBalance", "openingType"])

        return list(dict.fromkeys(fields))

    if tool_name == "get_customer_ledger":
        fields = ["ledgerName", "opening", "current", "closing", "period"]

        if any(word in q for word in ["transaction", "transactions", "statement", "entry", "entries"]):
            fields.append("transactions")

        return list(dict.fromkeys(fields))

    if tool_name == "get_stock_levels":
        fields = ["name"]

        if "hsn" in q:
            fields.append("hsnCode")

        if any(word in q for word in ["stock", "qty", "quantity", "jaththo", "satha", "closing"]):
            fields.append("closingQty")

        if "sku" in q:
            fields.append("sku")

        if "value" in q:
            fields.append("closingValue")

        if "rate" in q:
            fields.append("closingRate")

        if "low stock" in q:
            fields.append("isLowStock")

        if "out of stock" in q:
            fields.append("isOutOfStock")

        return list(dict.fromkeys(fields))

    if tool_name == "get_gst_summary":
        fields = ["category", "name"]

        asks_specific_field = False

        if "voucher count" in q or "voucher" in q:
            fields.append("voucherCount")
            asks_specific_field = True

        if "taxable" in q:
            fields.append("taxableAmount")
            asks_specific_field = True

        if "igst" in q:
            fields.append("igst")
            asks_specific_field = True

        if "cgst" in q:
            fields.append("cgst")
            asks_specific_field = True

        if "sgst" in q:
            fields.append("sgst")
            asks_specific_field = True

        if "cess" in q:
            fields.append("cess")
            asks_specific_field = True

        # Important: do not treat "taxable" as "tax".
        if re.search(r"\btax\b", q) or "total tax" in q:
            fields.append("tax")
            asks_specific_field = True

        if "invoice amount" in q:
            fields.append("invoiceAmount")
            asks_specific_field = True

        # Generic GST summary/report should return normal report columns.
        if not asks_specific_field:
            fields.extend([
                "voucherCount",
                "taxableAmount",
                "igst",
                "cgst",
                "sgst",
                "tax",
                "invoiceAmount",
            ])

        return list(dict.fromkeys(fields))

    if tool_name in {"get_tds_outstanding", "get_tcs_outstanding"}:
        fields = ["recordType", "name"]

        if "section" in q or re.search(r"\b(194c|194j|194i|206c)\b", q):
            fields.append("section")

        if "amount" in q:
            fields.append("amount")
            fields.append("totalAmount")

        if "outstanding" in q or "pending" in q or "payable" in q:
            fields.append("outstanding")
            fields.append("totalOutstanding")

        if "total" in q or "summary" in q:
            fields.extend(["totalAmount", "totalOutstanding", "total_rows", "total_pages"])

        fields.append("period")
        return list(dict.fromkeys(fields))

    return []


def compact_transactions(records: list[dict]) -> list[dict]:
    """
    Keep ledger transactions useful but prevent huge nested item dumps.
    It removes nested `items` and adds itemCount instead.
    """
    compacted_records = []

    for record in records:
        if not isinstance(record, dict):
            continue

        new_record = dict(record)
        transactions = new_record.get("transactions")

        if isinstance(transactions, list):
            compacted_txns = []

            for txn in transactions:
                if not isinstance(txn, dict):
                    continue

                items = txn.get("items", [])

                compacted_txns.append({
                    "id": txn.get("id"),
                    "refId": txn.get("refId"),
                    "date": txn.get("date"),
                    "txMode": txn.get("txMode"),
                    "txModeType": txn.get("txModeType"),
                    "ledgerName": txn.get("ledgerName"),
                    "invoiceNo": txn.get("invoiceNo"),
                    "cr": txn.get("cr"),
                    "dr": txn.get("dr"),
                    "balance": txn.get("balance"),
                    "narration": txn.get("narration"),
                    "itemCount": len(items) if isinstance(items, list) else 0,
                })

            new_record["transactions"] = compacted_txns

        compacted_records.append(new_record)

    return compacted_records

def project_records_by_fields(records: list, fields: list[str]) -> list:
    if not fields:
        return records

    projected = []

    for record in records:
        if not isinstance(record, dict):
            continue

        projected.append({
            field: record.get(field)
            for field in fields
            if field in record
        })

    return projected


def requested_gst_categories(query: str) -> list[str]:
    """
    Infer requested GST rows from the user query.
    This protects final output when the LLM/tool returns the full GST summary
    even though the user asked only B2B, grand total, exports, etc.
    """
    q = normalize_text(query)
    categories: list[str] = []

    def add(category: str):
        if category not in categories:
            categories.append(category)

    if re.search(r"\bb2b\b", q):
        add("b2b")

    if "b2c large" in q or "b2c-large" in q or ">= 2.5" in q or "2.5 lakh" in q:
        add("b2cLarge")

    if "b2c small" in q or "b2c-small" in q or "< 2.5" in q:
        add("b2cSmall")

    # Plain B2C without large/small is intentionally broad: keep both B2C rows.
    if re.search(r"\bb2c\b", q) and not any(c in categories for c in ["b2cLarge", "b2cSmall"]):
        add("b2cLarge")
        add("b2cSmall")

    if "export" in q or "exports" in q:
        add("exports")

    if "nil" in q or "nill" in q or "exempt" in q or "exempted" in q:
        add("nillRated")

    if "creditnotesregistered" in q or ("credit" in q and "registered" in q):
        add("creditNotesRegistered")

    if "creditnotesunregistered" in q or ("credit" in q and "unregistered" in q):
        add("creditNotesUnregistered")

    if "grand total" in q or "total gst" in q or "gst total" in q:
        add("grandTotal")

    return categories


def filter_gst_records_by_query(records: list[dict], query: str) -> list[dict]:
    """Filter GST rows deterministically based on category words in query."""
    requested = requested_gst_categories(query)

    if not requested:
        return records

    requested_set = set(requested)

    return [
        record for record in records
        if isinstance(record, dict) and record.get("category") in requested_set
    ]
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
        if tool_name == "get_gst_summary":
            records = filter_gst_records_by_query(
                records,
                f"{user_query or ''} {canonical_query or ''}",
            )

        fallback_fields = infer_requested_fields(user_query, tool_name)
        records = project_records_by_fields(records, fallback_fields)

        if tool_name == "get_customer_ledger":
            records = compact_transactions(records)

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

    user_query = state.get("canonical_query") or state.get("user_query", "")
    retrieved_tools = [
        tool_name for tool_name in state.get("retrieved_tools", [])
        if tool_name in tools_dict
    ]

    if not retrieved_tools:
        return {
            "router_decision": {
                "route": "unsupported",
                "required_tools": [],
                "query_parts": [user_query],
                "confidence": 0.0,
                "reason": "No tools were retrieved.",
            },
            "selected_tools": [],
            "query_parts": [user_query],
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
- customer/customer id/party/opening balance -> get_customer
- ledger/account statement/customer transactions/closing balance -> get_customer_ledger
- stock/inventory/product/HSN/SKU/closing quantity/low stock/out of stock -> get_stock_levels
- If no available tool can answer, use route "unsupported" and required_tools=[].
- Never invent tool names.
- When AVAILABLE TOOLS has multiple tools for a multi-intent query, prefer keeping all of them.
"""

    router_prompt = (
        router_prompt
        .replace("__USER_QUERY__", user_query)
        .replace("__RETRIEVED_TOOLS__", str(retrieved_tools))
    )

    messages = [
        SystemMessage(content=router_prompt),
        HumanMessage(content=user_query),
    ]

    try:
        response = await router_llm.ainvoke(messages)
        decision = json.loads(response.content)

    except Exception as e:
        print(f"Router parse/error fallback: {e}")

        decision = {
            "route": "tool_worker",
            "required_tools": retrieved_tools,
            "query_parts": state.get("query_parts", [user_query]),
            "confidence": 0.5,
            "reason": "Router failed, falling back to retrieved tools.",
        }

    route = decision.get("route", "tool_worker")
    required_tools = [
        tool_name for tool_name in decision.get("required_tools", [])
        if tool_name in retrieved_tools
    ]

    if route == "unsupported":
        selected_tools = []
    else:
        selected_tools = required_tools or retrieved_tools

        if len(retrieved_tools) > 1 and len(selected_tools) < len(retrieved_tools):
            selected_tools = retrieved_tools
            decision["required_tools"] = retrieved_tools
            decision["reason"] = (
                str(decision.get("reason", ""))
                + " | Multi-intent safety kept all retrieved tools."
            ).strip()

    print("Router selected tools:", selected_tools)

    return {
        "router_decision": decision,
        "selected_tools": selected_tools,
        "query_parts": decision.get("query_parts", state.get("query_parts", [user_query])),
    }