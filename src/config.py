from langchain_ollama import ChatOllama,OllamaEmbeddings
import os

# embedding_model = OllamaEmbeddings(model = "nomic-embed-text")
embedding_model = OllamaEmbeddings(model = "bge-m3")


normalizer_llm = ChatOllama(
    model="granite4.1:8b",
    temperature=0.0,
    keep_alive="30m",
    num_ctx=1024,
)

llm = ChatOllama(
    model="granite4.1:8b",
    temperature=0.0,
    keep_alive="30m",
    num_ctx=2048,
)

router_llm = ChatOllama(model="phi4-mini",temperature=0.0)

print("LLM and embedding model initialised!")


CHP1_API_BASE_URL = os.getenv("CHP1_API_BASE_URL","https://dev.chapter1.finance/ai/")
CHP1_API_TOKEN = os.getenv("CHP1_API_TOKEN", "")
CHP1_API_TIMEOUT = int(os.getenv("CHP1_API_TIMEOUT", "30"))
COMPANY_ID = int(os.getenv("COMPANY_ID", "355"))
