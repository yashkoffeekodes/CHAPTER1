from langchain_chroma import Chroma
from src.tool_doc import TOOL_DOCUMENTS
from src.config import embedding_model


try:
    emb_model = embedding_model

    vector_store = Chroma.from_documents(
        documents=TOOL_DOCUMENTS,
        embedding=emb_model,
        collection_name="tools_docs",
        persist_directory="./chroma_db"
    )
except Exception as e:
    print(f"Error creating vector store: {e}")
