from src.vector_store import vector_store
from src.tools_api import tools_dict
import re


def split_multi_intent_query(query: str) -> list[str]:
    split_pattern = (
        r"\s*,\s*and\s+|"
        r"\s*,\s*also\s+|"
        r"\s+and\s+|"
        r"\s+also\s+|"
        r"\s+aur\s+|"
        r"\s+ane\s+|"
        r"\s+ani\s+|"
        r",\s*|"
        r";\s*"
    )

    parts = re.split(split_pattern, query, flags=re.IGNORECASE)

    cleaned_parts = []

    for part in parts:
        part = part.strip()
        part = re.sub(
            r"^(and|also|aur|ane|ani)\s+",
            "",
            part,
            flags=re.IGNORECASE
        )

        if part:
            cleaned_parts.append(part)

    return cleaned_parts or [query]


def keyword_tool_override(part: str) -> list[str]:
    """
    Deterministic safety layer.
    Vector search can miss tools for short/mixed-language query parts.
    These overrides improve recall.
    """

    p = part.lower()
    selected = []

    # Sales invoice patterns:
    # A/0326/C0077, sale bill, customer bill, customer amount, etc.
    if (
        "sales" in p
        or "sale" in p
        or "customer" in p
        or "grahak" in p
        or "bill ka customer" in p
        or "customer amount" in p
        or re.search(r"\b[a-z]/\d{4}/[a-z]\d+\b", p, re.IGNORECASE)
    ):
        selected.append("get_sales_list")

    # Purchase invoice patterns:
    # PR-31, supplier, vendor, purchase bill, etc.
    if (
        "purchase" in p
        or "vendor" in p
        or "supplier" in p
        or "vikreta" in p
        or re.search(r"\bpr-\d+\b", p, re.IGNORECASE)
    ):
        selected.append("get_purchase_list")

    # Product / inventory patterns:
    if (
        "hsn" in p
        or "product" in p
        or "item" in p
        or "stock" in p
        or "inventory" in p
        or "sku" in p
        or "gst rate" in p
        or "closing quantity" in p
        or "closing qty" in p
    ):
        selected.append("get_product_list")

    return selected


async def retriever(query: str, tools_registry: dict = tools_dict, k: int = 2):
    try:
        print("Retrieving tools!")

        query_parts = split_multi_intent_query(query)
        print(f"Query parts: {query_parts}")

        selected_tool_names = []

        for part in query_parts:
            # 1. Deterministic override first
            override_tools = keyword_tool_override(part)

            if override_tools:
                print(f"Keyword override for query part '{part}': {override_tools}")

            for tool_name in override_tools:
                if tool_name in tools_registry:
                    selected_tool_names.append(tool_name)

            # 2. Vector search second
            results = await vector_store.asimilarity_search_with_score(part, k=k)

            print(f"\nScores for query part: {part}")

            for doc, score in results:
                tool_name = doc.metadata.get("tool_name")

                print(f"Tool={tool_name}, score={score}")

                if tool_name and tool_name in tools_registry:
                    selected_tool_names.append(tool_name)

        unique_tool_names = []

        for name in selected_tool_names:
            if name not in unique_tool_names:
                unique_tool_names.append(name)

        selected_tools = [tools_registry[name] for name in unique_tool_names]

        print(f"Final selected tools: {unique_tool_names}")

        return selected_tools

    except Exception as e:
        print(f"Error in retriever: {e}")
        return []