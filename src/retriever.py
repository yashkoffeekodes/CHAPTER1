from src.vector_store import vector_store
from src.tools import tools_dict
import re
import asyncio

def split_multi_intent_query(query: str) -> list[str]:
    split_pattern = (
        r"\s*,\s*and\s+|"
        r"\s*,\s*also\s+|"
        r"\s+and\s+|"
        r"\s+also\s+|"
        r"\s+aur\s+|"
        r"\s+ane\s+|"
        r",\s*|"
        r";\s*"
    )

    parts = re.split(split_pattern, query, flags=re.IGNORECASE)

    cleaned_parts = []
    for part in parts:
        part = part.strip()
        part = re.sub(r"^(and|also|aur|ane)\s+", "", part, flags=re.IGNORECASE)

        if part:
            cleaned_parts.append(part)

    return cleaned_parts or [query]

async def retriever(query: str, tools_registry: dict=tools_dict, k: int=1): 
    try:
        print("Retriving tools!")

        query_parts = split_multi_intent_query(query)
        print(f"Query parts: {query_parts}")
        selected_tools_names = []
        selected_tools = []
        for part in query_parts:
            docs = await vector_store.asimilarity_search(part, k=k)
            for doc in docs:
                tool_name = doc.metadata.get("tool_name")
                if tool_name:
                    selected_tools_names.append(tool_name)

                    tool = tools_registry.get(tool_name)
                    if tool:
                        selected_tools.append(tool)
        return selected_tools

    except Exception as e:
        return f"Error in retriever: {e}"
        
