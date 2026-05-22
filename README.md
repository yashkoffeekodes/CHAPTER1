# Chapter1 AI Assistant

An asynchronous **ERP & Accounting AI Assistant** built with **LangGraph**, **LangChain**, **FastAPI**, **NVIDIA AI Endpoints**, and **ChromaDB**.

The assistant understands ERP/accounting queries, breaks multi-intent questions into smaller semantic parts, retrieves relevant ERP tools, binds only those tools to the LLM, executes tool calls, and returns a structured **dynamic JSON response** suitable for API/frontend usage.

---

## Features

- **LangGraph workflow** for structured agent execution
- **FastAPI backend** with a `/chat` endpoint
- **Dynamic JSON API responses**
- **Semantic tool retrieval** using ChromaDB vector search
- **Multi-intent query decomposition** before semantic retrieval
- **Dynamic tool binding** so the LLM only receives relevant tools
- **Few-shot worker prompt** for better multi-tool calling and filtering
- **Async execution** using `async` / `await`
- **Supervisor routing node** to decide whether to finish, retry, or call tools
- **NVIDIA ChatNVIDIA model** for reasoning and tool calling
- **NVIDIA embeddings** for tool-card vector search
- Supports **multi-intent ERP queries** (English, Hindi, Gujarati)

---

## Architecture

```text
User / Postman / Frontend
   |
   v
FastAPI /chat endpoint
   |
   v
Initial LangGraph State
   |
   v
Semantic Search Node
   |  - Splits multi-intent query into smaller parts
   |  - Searches ChromaDB tool cards
   v
Worker / Chatbot Node
   |  - Binds selected tools
   |  - Uses few-shot prompt for JSON output
   v
Supervisor Node
   |  - Routes between Worker, Tools, or END
   v
Tools Node
   |  - Executes ERP tools
   v
Structured Dynamic JSON Response

Tech Stack

    Python 3.11+

    FastAPI / Uvicorn

    LangChain / LangGraph

    ChromaDB

    NVIDIA AI Endpoints (LLM & Embeddings)

    Pydantic

Installation

    Clone the repository:

Bash

   git clone [https://github.com/yashkoffeekodes/CHAPTER1.git](https://github.com/yashkoffeekodes/CHAPTER1.git)
   cd CHAPTER1

    Setup virtual environment:

Bash

   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate

    Install dependencies:

Bash

   pip install -r requirements.txt

    Environment Variables:
    Create a .env file in the root:

Code snippet

   NVIDIA_API_KEY=your_nvidia_api_key_here

Running the API

Start the backend:
Bash

uvicorn fast_main:app --reload

The API will be available at http://127.0.0.1:8000.
Testing with Postman

POST http://127.0.0.1:8000/chat

Body:
JSON

{
  "query": "Find all sales invoices where customer city is Silvassa, and show receipt vouchers where payment mode is CASH."
}

Author

Built by Yash Sheth as a LangChain + LangGraph ERP assistant project.


---

