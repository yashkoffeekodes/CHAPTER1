from langchain_chroma import Chroma
from src.config import embedding_model
from src.tool_doc import tool_docs
from src.tool import tools_dict



try:
        
    emb_model = embedding_model

    vectore_store = Chroma.from_documents(
        documents=tool_docs,
        embedding=emb_model,
        persist_directory="./chroma_db",
        collection_name="tool_cards"
    )
    print("Vector store created successfully!")

except Exception as e:
    print(f"Error creating vector store: {e}")
    