from src.vectorstore import vectore_store
import asyncio

from src.tool_doc import tool_docs
from src.tool import tools_dict

async def retriever(query:str,tools_registry:dict=tools_dict,k:int=5):
    try:
        """
        This function searches the list of tool names to find the most similar tools to the user's query.
        """
        print(f"Retrieving tools based on the user's query : {query}")
        retriver_tools = await vectore_store.asimilarity_search(query,k=k)
        retrieval_tool_name = [tool.metadata.get("tool_name") for tool in retriver_tools if tool.metadata.get("tool_name")]

        tools_list = list(dict.fromkeys(retrieval_tool_name))
        retrival_list = [tools_registry[name] for name in tools_list if name in tools_registry]
        
        return retrival_list
    except Exception as e:
        print(f"Error in retriever: {e}")
    
  