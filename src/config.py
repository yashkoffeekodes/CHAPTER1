from langchain_ollama import ChatOllama,OllamaEmbeddings
import os

embedding_model = OllamaEmbeddings(model = "nomic-embed-text")

# llm = ChatOllama(model="qwen3:30b-a3b-q4_K_M", temperature=0.0)
llm = ChatOllama(model="qwen3:14b-q4_K_M", temperature=0.0)


print("LLM and embedding model initialised!")


CHP1_API_BASE_URL = os.getenv("CHP1_API_BASE_URL","https://dev.chapter1.finance/ai/")
CHP1_API_TOKEN = os.getenv("CHP1_API_TOKEN", "")
CHP1_API_TIMEOUT = int(os.getenv("CHP1_API_TIMEOUT", "30"))
COMPANY_ID = int(os.getenv("COMPANY_ID", "355"))
