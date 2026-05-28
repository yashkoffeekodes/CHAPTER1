from langchain_ollama import ChatOllama,OllamaEmbeddings
from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv
load_dotenv()
# embedding_model = OllamaEmbeddings(model = "nomic-embed-text")

token = os.environ.get("GROQ_API_KEY")
embedding_model = OllamaEmbeddings(model = "bge-m3")


normalizer_llm = ChatOllama(
    model="granite4.1:8b",
    temperature=0.0,
    keep_alive="30m",
    num_ctx=1024,
)



# llm = ChatGroq(
#     model="llama-3.3-70b-versatile",
#     temperature=0.0,
#     api_key=token,
# )

llm = ChatOllama(
    model="granite4.1:8b",
    temperature=0.0,
    keep_alive="30m",
    num_ctx=2048,
)

# router_llm = ChatOllama(model="phi4-mini",temperature=0.0)

print("LLM and embedding model initialised!")


CHP1_API_BASE_URL = os.getenv("CHP1_API_BASE_URL","https://dev.chapter1.finance/aiAnalytics/")
CHP1_API_TOKEN = os.getenv("CHP1_API_TOKEN", "")
# CHP1_API_TIMEOUT = int(os.getenv("CHP1_API_TIMEOUT", "30"))
CHP1_API_TIMEOUT = int(os.getenv("CHP1_API_TIMEOUT", "10"))

COMPANY_ID = int(os.getenv("COMPANY_ID", "355"))

