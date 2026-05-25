from langchain_ollama import ChatOllama,OllamaEmbeddings


embedding_model = OllamaEmbeddings(model = "nomic-embed-text")

# llm = ChatOllama(model="qwen3:30b-a3b-q4_K_M", temperature=0.0)
llm = ChatOllama(model="qwen3:14b-q4_K_M", temperature=0.0)


print("LLM and embedding model initialised!")