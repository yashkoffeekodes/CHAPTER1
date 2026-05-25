# Chapter1_Assist

An asynchronous **LangGraph-powered ERP and Accounting AI Assistant** with a **FastAPI backend**.

This project demonstrates how an AI assistant can answer ERP-style business queries by:
- understanding the user's query,
- retrieving the most relevant ERP tools using semantic search,
- calling only the required tools,
- filtering structured ERP/accounting data,
- and returning a compact JSON response through a REST API.

The project currently uses dummy/static ERP data, but the architecture is designed so the tools can later be connected to real APIs or a database.

---

## Features

- FastAPI REST API
- LangGraph workflow orchestration
- LangChain tool calling
- ChromaDB semantic tool retrieval
- Ollama local LLM support
- Ollama embedding model support
- Multi-tool query handling
- Structured JSON responses
- Step-level execution timing logs
- Tool filtering for:
  - purchase invoices
  - sales invoices
  - product/inventory records
  - negative stock
  - positive stock
  - zero stock
  - outstanding invoices
  - state-based invoice filtering

---

## Tech Stack

- Python
- FastAPI
- Uvicorn
- LangGraph
- LangChain
- ChromaDB
- Ollama
- Pydantic

---

## Project Structure

```text
.
├── fast_main.py          # FastAPI application entry point
├── src/
│   ├── config.py         # LLM and embedding model configuration
│   ├── graph.py          # LangGraph workflow definition
│   ├── nodes.py          # Semantic search and chat model nodes
│   ├── retriever.py      # Semantic tool retriever
│   ├── schema.py         # LangGraph state schemas
│   ├── tool_doc.py       # Tool documentation used for vector search
│   ├── tools.py          # ERP tools for purchases, sales, and products
│   ├── vector_store.py   # ChromaDB vector store setup
│   └── dummy.py          # Dummy ERP/accounting data
└── README.md
```

---

## How It Works

The assistant follows this LangGraph flow:

```text
START
  ↓
semantic_search
  ↓
chat_model
  ↓
tools
  ↓
chat_model
  ↓
END
```

### 1. Semantic Search Node

The user query is split into intent-like parts. Each part is searched against ChromaDB tool documentation to find the most relevant ERP tools.

Example:

```text
Show me all purchase invoices from Maharashtra and list the items that have a closing quantity of 0.
```

This can retrieve:

```text
get_purchase_list
get_products_list
```

### 2. Chat Model Node

The LLM receives the original user query and the retrieved tools.

On the first pass, it decides which tools to call.

Example tool calls:

```json
[
  {
    "name": "get_purchase_list",
    "args": {
      "state": "Maharashtra"
    }
  },
  {
    "name": "get_products_list",
    "args": {
      "zero_stock": true
    }
  }
]
```

### 3. Tools Node

The selected tools execute and return filtered ERP data.

### 4. Final Chat Model Response

The LLM generates a compact JSON response using only the tool output.

---

## API Endpoints

### Health Check

```http
GET /
```

Response:

```json
{
  "message": "ERP Assistant API is running"
}
```

### Chat Endpoint

```http
POST /chat
```

Request body:

```json
{
  "query": "Show me all purchase invoices from Maharashtra."
}
```

Response format:

```json
{
  "response": {
    "success": true,
    "status": "success",
    "query": "Show me all purchase invoices from Maharashtra.",
    "tools_used": ["get_purchase_list"],
    "data": {
      "get_purchase_list": []
    },
    "summary": "Found matching purchase invoices.",
    "errors": []
  },
  "timings": [
    {
      "node": "semantic_search",
      "duration_sec": 0.031
    },
    {
      "node": "chat_model",
      "duration_sec": 18.704
    },
    {
      "node": "tools",
      "duration_sec": 0.003
    }
  ],
  "total_time_sec": 19.234
}
```

---

## Example Queries

```text
Show me all purchase invoices from Maharashtra.
```

```text
Show purchase invoices from Karnataka and products with negative stock.
```

```text
Show me all sales invoices from Gujarat.
```

```text
List products with closing quantity of 0.
```

```text
Find purchase invoice PR-32.
```

```text
Show outstanding purchase invoices.
```

---

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/yashkoffeekodes/CHAPTER1.git
cd CHAPTER1
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate
```

For Windows:

```bash
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install fastapi uvicorn langchain langgraph langchain-ollama langchain-chroma chromadb pydantic
```

If you already have a `requirements.txt`, use:

```bash
pip install -r requirements.txt
```

### 4. Install and Run Ollama

Install Ollama from:

```text
https://ollama.com
```

Pull the required models:

```bash
ollama pull qwen3:14b-q4_K_M
ollama pull nomic-embed-text
```

### 5. Run the API

If your FastAPI file is named `fast_main.py`:

```bash
uvicorn fast_main:app --reload
```

If your file is named `main.py`:

```bash
uvicorn main:app --reload
```

The API will run at:

```text
http://127.0.0.1:8000
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

---

## Testing with cURL

```bash
curl -X POST "http://127.0.0.1:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me all purchase invoices from Maharashtra."}'
```

---

## Important GitHub Note

Do not push your virtual environment or local vector database files.

Add this to `.gitignore`:

```gitignore
venv/
__pycache__/
*.pyc
.env
chroma_db/
```

If `venv/` was already pushed, remove it from Git tracking:

```bash
git rm -r --cached venv
git add .gitignore
git commit -m "Remove virtual environment from tracking"
git push
```

---

## Current Limitations

- The project currently uses dummy/static ERP data.
- Final response generation still uses the LLM, which can be slow for large tool outputs.
- A future optimization is to add a deterministic Python `finalizer_node` after tool execution.
- Authentication is not implemented yet.
- Database/API integration is planned for future versions.

---

## Future Improvements

- Connect tools to real ERP APIs or a database
- Add authentication and user sessions
- Add deterministic Python finalizer for faster JSON responses
- Add pagination for large results
- Add better error handling and logging
- Add Docker support
- Add automated tests
- Add frontend UI
- Add LangSmith tracing

---

## Example Output

```json
{
  "success": true,
  "status": "success",
  "query": "Show me all purchase invoices from Maharashtra and list the items that have a closing quantity of 0.",
  "tools_used": ["get_purchase_list", "get_products_list"],
  "data": {
    "get_purchase_list": [
      {
        "invoiceNo": "PR-32",
        "invoiceDate": "31-03-2026",
        "billToName": "Amazon seller services private limited-maharashtra",
        "billToState": "Maharashtra",
        "taxableAmount": "7611",
        "netAmount": "8981",
        "outstanding": "8981",
        "status": "New"
      }
    ],
    "get_products_list": [
      {
        "id": 126,
        "name": "Books",
        "uom": "NOS",
        "hsn": "49011010",
        "closingQty": 0
      }
    ]
  },
  "summary": "Found purchase invoices from Maharashtra and items with closing quantity 0.",
  "errors": []
}
```

---

## Author

**Yash Sheth**

GitHub: [@yashkoffeekodes](https://github.com/yashkoffeekodes)

---

## License

This project is currently for learning, experimentation, and portfolio demonstration. Add a license file if you plan to make it open source.
