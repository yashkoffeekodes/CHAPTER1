from src.vectorstore import vectore_store
from src.tool import tools_dict
import re


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


async def retriever(query: str, tools_registry: dict = tools_dict, k: int = 7):
    try:
        print(f"Retrieving tools based on the user's query : {query}")

        query_parts = split_multi_intent_query(query)
        print(f"Query parts detected: {query_parts}")

        final_tool_names = []

        for part in query_parts:
            docs = await vectore_store.asimilarity_search(part, k=2)

            tool_names = [
                doc.metadata.get("tool_name")
                for doc in docs
                if doc.metadata.get("tool_name")
            ]

            print(f"Tools for query part '{part}': {tool_names}")
            final_tool_names.extend(tool_names)

        final_tool_names = list(dict.fromkeys(final_tool_names))
        final_tool_names = final_tool_names[:k]

        print(f"Final retrieved tool names: {final_tool_names}")

        return [
            tools_registry[name]
            for name in final_tool_names
            if name in tools_registry
        ]

    except Exception as e:
        print(f"Error in retriever: {e}")
        return []




# from src.vectorstore import vectore_store
# from src.tool import tools_dict
# import re


# def split_multi_intent_query(query: str) -> list[str]:
#     """
#     Splits a user query into smaller semantic parts.
#     This avoids one long query hiding smaller intents.
#     """

#     parts = re.split(
#         r"\s+and\s+|,\s*|;\s*|\s+aur\s+|\s+ane\s+",
#         query,
#         flags=re.IGNORECASE
#     )

#     cleaned_parts = [
#         part.strip()
#         for part in parts
#         if part.strip()
#     ]

#     return cleaned_parts or [query]


# async def retriever(query: str, tools_registry: dict = tools_dict, k: int = 7):
#     try:
#         print(f"Retrieving tools based on the user's query : {query}")

#         query_parts = split_multi_intent_query(query)

#         print(f"Query parts detected: {query_parts}")

#         final_tool_names = []

#         # Search each smaller intent separately
#         for part in query_parts:
#             docs = await vectore_store.asimilarity_search(part, k=k)

#             tool_names = [
#                 doc.metadata.get("tool_name")
#                 for doc in docs
#                 if doc.metadata.get("tool_name")
#             ]

#             final_tool_names.extend(tool_names)

#         # Also search the full query as backup
#         full_query_docs = await vectore_store.asimilarity_search(query, k=3)

#         full_query_tool_names = [
#             doc.metadata.get("tool_name")
#             for doc in full_query_docs
#             if doc.metadata.get("tool_name")
#         ]

#         final_tool_names.extend(full_query_tool_names)

#         # Remove duplicates while keeping order
#         final_tool_names = list(dict.fromkeys(final_tool_names))

#         print(f"Final retrieved tool names: {final_tool_names}")

#         retrieved_tools = [
#             tools_registry[name]
#             for name in final_tool_names
#             if name in tools_registry
#         ]

#         return retrieved_tools

#     except Exception as e:
#         print(f"Error in retriever: {e}")
#         return []


# # from src.vectorstore import vectore_store
# # import asyncio

# # from src.tool_doc import tool_docs
# # from src.tool import tools_dict

# # async def retriever(query:str,tools_registry:dict=tools_dict,k:int=5):
# #     try:
# #         """
# #         This function searches the list of tool names to find the most similar tools to the user's query.
# #         """
# #         print(f"Retrieving tools based on the user's query : {query}")
# #         retriver_tools = await vectore_store.asimilarity_search(query,k=k)
# #         retrieval_tool_name = [tool.metadata.get("tool_name") for tool in retriver_tools if tool.metadata.get("tool_name")]

# #         tools_list = list(dict.fromkeys(retrieval_tool_name))
# #         retrival_list = [tools_registry[name] for name in tools_list if name in tools_registry]
        
# #         return retrival_list
# #     except Exception as e:
# #         print(f"Error in retriever: {e}")
    
