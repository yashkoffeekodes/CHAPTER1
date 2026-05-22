from langchain_chroma import Chroma
from src.config import embedding_model
from src.tool_doc import tool_docs
from src.few_shot_prompt import few_shot_examples

emb_model = embedding_model
vector_store = None
examples_store = None
try:
    # Tool cards collection
    vector_store = Chroma(
        collection_name="tool_cards",
        embedding_function=emb_model,
        persist_directory="./chroma_db"
    )
    if vector_store._collection.count() == 0:
        vector_store = Chroma.from_documents(
            documents=tool_docs,
            embedding=emb_model,
            persist_directory="./chroma_db",
            collection_name="tool_cards"
        )
        print("Tool store created fresh.")
    else:
        print("Tool store loaded from disk.")

except Exception as e:
    print(f"Error with tool vector store: {e}")

try:
    # Few-shot examples collection
    examples_store = Chroma(
        collection_name="few_shot_examples",
        embedding_function=emb_model,
        persist_directory="./chroma_db_examples"
    )
    if examples_store._collection.count() == 0:
        examples_store = Chroma.from_documents(
            documents=few_shot_examples,
            embedding=emb_model,
            persist_directory="./chroma_db_examples",
            collection_name="few_shot_examples"
        )
        print("Examples store created fresh.")
    else:
        print("Examples store loaded from disk.")

except Exception as e:
    print(f"Error with examples vector store: {e}")