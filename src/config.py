from langchain_nvidia_ai_endpoints import ChatNVIDIA, NVIDIAEmbeddings
from dotenv import load_dotenv
import os


try:
    load_dotenv()

    NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
    llm = ChatNVIDIA(model="nvidia/llama-3.3-nemotron-super-49b-v1.5",api_key=NVIDIA_API_KEY,max_tokens=4096)

    # llm = ChatNVIDIA(model="openai/gpt-oss-120b",api_key=NVIDIA_API_KEY)
    # llm = ChatNVIDIA(model="qwen/qwen3-next-80b-a3b-instruct",api_key=NVIDIA_API_KEY)

    # llm = ChatNVIDIA(model="meta/llama-3.3-70b-instruct",api_key=NVIDIA_API_KEY)
    embedding_model = NVIDIAEmbeddings(model="nvidia/nv-embedqa-e5-v5", api_key=NVIDIA_API_KEY)
    print("Embedding model and LLM loaded successfully!")
except Exception as e:
    print(f"Error loading models: {e}")